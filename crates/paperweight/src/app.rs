//! Application orchestration for the CLI.
//!
//! `run_cli` owns the process boundary (argument parsing and exit status).
//! This module owns everything between: it installs the Ctrl-C cancel,
//! validates the gateway environment and model selection, resolves the prompt source and its name
//! (the embedded paperweight prompt by default, `--prompt` from disk otherwise),
//! loads the paper markdown from the SQLite paper store, and runs the prompt
//! through the Harness against the gateway. The Harness stages the paper at the
//! prompt's declared input and hands back its declared output, which is written
//! to `--output`, or to stdout when no path is given.

use std::ffi::OsStr;
use std::fmt;
use std::io::{self, Write as _};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;

use anyhow::{Context, Result, bail};
use clap::Parser;
use harness::plugin::{HostContext, HostServices, PackageRegistry};
use harness::record::{
    Record, RecordKind, RecorderFuture, RunId, RunMeta, RunOutcome, RunRecorder,
};
use harness::vfs::VfsRef;
use harness::{BoxFuture, Harness, HostSnapshot, OutputError, RunControl, Timer};
use harness_gateway_client::{GatewayBroker, GatewayEndpoint, SecretString};
use paperstore::{PaperNum, StorageBackend};
use paperstore_sqlite::SqliteBackend;

/// The embedded paperweight prompt, vendored from the runvil prompts.
const DEFAULT_PROMPT: &str = include_str!("../paperweight.md");

/// The name the embedded prompt runs under.
const DEFAULT_PROMPT_NAME: &str = "paperweight";

/// The command-line interface; `run_cli` sets the program name.
#[derive(Debug, Parser)]
#[command(version, about = "Run a runvil prompt against a WG21 paper")]
pub(crate) struct Cli {
    /// The WG21 paper number to analyze, resolved through the paper store.
    pub(crate) paper: PaperNum,
    /// Write the prompt's output to PATH instead of stdout.
    #[arg(long, value_name = "PATH")]
    pub(crate) output: Option<PathBuf>,
    /// Read the prompt from PATH instead of the embedded paperweight prompt.
    #[arg(long, value_name = "PATH")]
    pub(crate) prompt: Option<PathBuf>,
    /// The gateway model id the prompt's model roles bind to; defaults to the
    /// first chat model the gateway lists.
    #[arg(long, value_name = "ID")]
    pub(crate) model: Option<String>,
    /// Also print every tool call with its arguments, every tool result in
    /// full, Lua log messages, and model replies to stderr.
    #[arg(short, long)]
    pub(crate) verbose: bool,
}

/// A single analysis run: what to read, where to write, and how to report.
pub(crate) struct RunRequest<'a> {
    /// The paper to analyze.
    pub(crate) paper: &'a PaperNum,
    /// Where the analysis report is written; stdout when `None`.
    pub(crate) output: Option<&'a Path>,
    /// An optional prompt file overriding the embedded default.
    pub(crate) prompt: Option<&'a Path>,
    /// The gateway model id to bind; `None` binds the gateway's first chat
    /// model.
    pub(crate) model: Option<&'a str>,
    /// Print tool calls, tool results, Lua logs, and replies to stderr.
    pub(crate) verbose: bool,
}

impl std::fmt::Debug for RunRequest<'_> {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("RunRequest")
            .field("paper", &self.paper)
            .field("output", &self.output)
            .field("prompt", &self.prompt)
            .field("model", &self.model)
            .field("verbose", &self.verbose)
            .finish_non_exhaustive()
    }
}

/// The run was closed by Ctrl-C before it completed.
#[derive(Debug)]
pub(crate) struct Cancelled;

impl fmt::Display for Cancelled {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("run cancelled")
    }
}

impl std::error::Error for Cancelled {}

/// Runs one analysis using the gateway configuration read from the environment.
///
/// # Errors
/// Returns an error if either gateway variable is unset or blank, the paper
/// cannot be loaded (`WG21_DATA_DIR` unset, or the number missing from the
/// store or without converted markdown), the gateway model list cannot be
/// fetched or omits the selected model, the run fails (including a gateway
/// that lists no chat model), the run is cancelled ([`Cancelled`]), the prompt
/// did not produce its declared output, or the `--prompt` path has no usable
/// file name.
pub(crate) async fn run(request: RunRequest<'_>) -> Result<()> {
    let RunRequest {
        paper,
        output,
        prompt,
        model,
        verbose,
    } = request;
    let name = prompt_name(prompt)?;
    let (base_url, key) = gateway_from_env(&name)?;
    let model = selected_model(model);

    let source = match prompt {
        Some(path) => tokio::fs::read_to_string(path)
            .await
            .with_context(|| format!("read prompt file {}", path.display()))?,
        None => DEFAULT_PROMPT.to_owned(),
    };
    // Load before the launch: a store miss fails fast, before any network
    // call. The lookup is one indexed SQLite query plus one file read,
    // trivial next to the model calls that follow.
    let paper_md = load_paper_md(&SqliteBackend::from_env()?, paper)?;
    let endpoint = GatewayEndpoint::new(&format!("{base_url}/v1"))
        .context("read the gateway URL from PROMPTFORGE_GATEWAY_URL")?;
    let key =
        SecretString::new(key).context("read the gateway key from PROMPTFORGE_GATEWAY_API_KEY")?;

    let harness = Harness::new(
        Arc::new(ProgressRecorder { verbose }),
        Arc::new(GatewayBroker::new(endpoint, key)),
        Arc::new(TokioTimer),
        // No Plugin (web, user-input, MCP) is installed. The embedded
        // paperweight prompt declares none and calls no Plugin tools, but a
        // `--prompt` file that lists one under `plugins:` makes it required,
        // so its run fails at startup naming the missing Plugin.
        Arc::new(HostContext::new(
            PackageRegistry::new(),
            HostServices::new(),
        )),
        HostServices::new(),
    );
    let ctrl_c = tokio::spawn(cancel_on_ctrl_c(harness.control()));
    let report = harness
        .run(harness::RunRequest {
            name: name.clone(),
            source,
            args: String::new(),
            input_text: Some(paper_md),
            vfs: VfsRef::default(),
            host: HostSnapshot {
                selected_model: model,
                workspace_roots: Vec::new(),
            },
        })
        .await;
    ctrl_c.abort();
    let report = report.with_context(|| format!("run the {name} prompt"))?;

    match report.outcome {
        RunOutcome::Completed { .. } => {}
        RunOutcome::Failed { kind, message } => bail!("run failed ({kind}): {message}"),
        RunOutcome::Cancelled => return Err(Cancelled.into()),
    }
    let report = match report.output {
        Ok(report) => report,
        Err(error @ OutputError::Missing { .. }) => {
            return Err(error).context("the prompt did not produce its declared output");
        }
        Err(error) => return Err(error).context("read the run's declared output"),
    };
    match output {
        Some(path) => {
            tokio::fs::write(path, &report)
                .await
                .with_context(|| format!("write the report to {}", path.display()))?;
            println!("{}", path.display());
        }
        None => write_stdout(report.as_bytes())?,
    }
    Ok(())
}

/// Cancels the run on the first Ctrl-C.
///
/// A failure to register the signal listener is reported to stderr rather
/// than discarded: the run simply stays non-cancellable in that case.
async fn cancel_on_ctrl_c(control: RunControl) {
    match tokio::signal::ctrl_c().await {
        Ok(()) => control.cancel(),
        Err(error) => {
            eprintln!("warning: cannot listen for Ctrl-C, run is not cancellable: {error}");
        }
    }
}

/// Sleeps on tokio's timer.
struct TokioTimer;

impl Timer for TokioTimer {
    fn sleep(&self, seconds: f64) -> BoxFuture<()> {
        // The Engine refuses a timeout that `Duration` cannot hold before it
        // issues the effect, so the zero fallback never fires.
        let duration = Duration::try_from_secs_f64(seconds).unwrap_or(Duration::ZERO);
        Box::pin(tokio::time::sleep(duration))
    }
}

/// A recorder that prints each event of the run to stderr as the Harness
/// records it, and keeps nothing.
struct ProgressRecorder {
    /// Print each event's [`detail_lines`] after its progress line.
    verbose: bool,
}

impl RunRecorder for ProgressRecorder {
    fn begin_run(&self, _meta: RunMeta) -> RecorderFuture<'_, RunId> {
        Box::pin(async { Ok(RunId::from_raw(1)) })
    }

    fn append(&self, _run: RunId, record: Record) -> RecorderFuture<'_, ()> {
        if record.kind == RecordKind::Event {
            print_progress(&record.payload, self.verbose);
        }
        Box::pin(async { Ok(()) })
    }

    fn end_run(&self, _run: RunId, _outcome: RunOutcome) -> RecorderFuture<'_, ()> {
        Box::pin(async { Ok(()) })
    }
}

/// Writes one progress line for an engine event to stderr, followed by its
/// [`detail_lines`] when `verbose`.
fn print_progress(event: &serde_json::Value, verbose: bool) {
    let mut stderr = io::stderr().lock();
    // Progress is a side channel, so a failed write to stderr is
    // deliberately dropped rather than surfaced.
    let _ignored = writeln!(
        stderr,
        "[{}] {}: {}",
        event_field(event, "execution"),
        event_field(event, "section"),
        event_field(event, "kind"),
    );
    if verbose {
        for line in detail_lines(event) {
            let _ignored = writeln!(stderr, "{line}");
        }
    }
}

/// Returns the indented detail lines `--verbose` prints for an engine event.
///
/// A tool call shows its id, tool name, and JSON arguments; a tool result
/// shows the id of the call it answers and its full content, which carries
/// the error text when the call failed. Lua log messages and model replies
/// are shown too. Every other kind has no detail lines.
fn detail_lines(event: &serde_json::Value) -> Vec<String> {
    let text = |name: &str| {
        event
            .get(name)
            .and_then(serde_json::Value::as_str)
            .unwrap_or("")
    };
    match text("kind") {
        "assistant_tool_calls" => event
            .get("calls")
            .and_then(serde_json::Value::as_array)
            .map(|calls| {
                calls
                    .iter()
                    .map(|call| {
                        let field = |name: &str| {
                            call.get(name)
                                .and_then(serde_json::Value::as_str)
                                .unwrap_or("-")
                        };
                        let arguments = call
                            .get("arguments")
                            .map_or_else(|| "null".to_owned(), serde_json::Value::to_string);
                        format!("    -> call {} {} {arguments}", field("id"), field("name"))
                    })
                    .collect()
            })
            .unwrap_or_default(),
        "tool_result" => {
            let mut lines = vec![format!(
                "    <- result {} {}:",
                text("tool_call_id"),
                text("alias")
            )];
            lines.extend(indented(text("content")));
            lines
        }
        "lua" => vec![format!("    lua: {}", text("message"))],
        "assistant_reply" => {
            let mut lines = vec!["    reply:".to_owned()];
            lines.extend(indented(text("text")));
            lines
        }
        _ => Vec::new(),
    }
}

/// Returns each line of `text` indented under a detail header.
fn indented(text: &str) -> impl Iterator<Item = String> + '_ {
    text.lines().map(|line| format!("        {line}"))
}

/// Returns the string field `name` of the event's payload, or `-`.
fn event_field<'a>(event: &'a serde_json::Value, name: &str) -> &'a str {
    event
        .get(name)
        .and_then(serde_json::Value::as_str)
        .unwrap_or("-")
}

/// Writes bytes to stdout verbatim, flushing before return.
///
/// Verbatim (no added newline) keeps the output pipe-friendly; the explicit
/// flush guarantees delivery before the process exits.
fn write_stdout(bytes: &[u8]) -> Result<()> {
    let mut stdout = io::stdout().lock();
    stdout
        .write_all(bytes)
        .and_then(|()| stdout.flush())
        .context("write the report to stdout")
}

/// Loads the converted markdown for `num` through `backend`.
///
/// `meta` runs first so an unknown number surfaces `MissingPaper`; a bare
/// `paper_md` lookup reports the same rowless case as `MissingMarkdown`,
/// which would misname the failure.
fn load_paper_md(backend: &impl StorageBackend, num: &PaperNum) -> paperstore::Result<String> {
    backend.meta(num)?;
    backend.paper_md(num)
}

/// Returns the explicit model selection, trimmed.
///
/// A missing or blank selection is `None`, which the harness resolves to the
/// first model in the catalog binding.
fn selected_model(model: Option<&str>) -> Option<String> {
    model
        .map(str::trim)
        .filter(|model| !model.is_empty())
        .map(str::to_owned)
}

/// Returns the name the run takes from its prompt: the `--prompt` file stem,
/// or [`DEFAULT_PROMPT_NAME`] for the embedded prompt.
///
/// The harness launches an agent by the stem of its file in the agents
/// directory, so the prompt is written there under this name.
fn prompt_name(prompt: Option<&Path>) -> Result<String> {
    let Some(path) = prompt else {
        return Ok(DEFAULT_PROMPT_NAME.to_owned());
    };
    path.file_stem()
        .and_then(OsStr::to_str)
        .filter(|stem| !stem.is_empty())
        .map(str::to_owned)
        .with_context(|| format!("the prompt path {} has no usable file name", path.display()))
}

/// Reads the gateway environment, requiring both variables.
///
/// The prompt `name` binds its models through the gateway, so there is no
/// local-only mode: a missing credential is a startup error naming both
/// variables rather than a silent downgrade.
fn gateway_from_env(name: &str) -> Result<(String, String)> {
    let endpoint = env_optional("PROMPTFORGE_GATEWAY_URL")?;
    let token = env_optional("PROMPTFORGE_GATEWAY_API_KEY")?;
    let endpoint = endpoint.map(|value| gateway_origin(&value));
    let token = token.map(|value| value.trim().to_owned());
    match (endpoint, token) {
        (Some(endpoint), Some(token)) if !endpoint.is_empty() && !token.is_empty() => {
            Ok((endpoint, token))
        }
        _ => bail!(
            "PROMPTFORGE_GATEWAY_URL and PROMPTFORGE_GATEWAY_API_KEY must both be set: \
             the {name} prompt binds its models through the gateway"
        ),
    }
}

/// Returns the gateway origin for `url`: trimmed, without trailing slashes
/// or a `/v1` suffix, because the harness appends `/v1` itself.
fn gateway_origin(url: &str) -> String {
    let url = url.trim().trim_end_matches('/');
    url.strip_suffix("/v1")
        .unwrap_or(url)
        .trim_end_matches('/')
        .to_owned()
}

/// Reads an optional environment variable, distinguishing an absent variable
/// (`Ok(None)`) from a present-but-unreadable one.
///
/// A missing variable is expected and yields `None`; a non-Unicode value is a
/// real error and is propagated with context rather than silently dropped.
fn env_optional(name: &str) -> Result<Option<String>> {
    match std::env::var(name) {
        Ok(value) => Ok(Some(value)),
        Err(std::env::VarError::NotPresent) => Ok(None),
        Err(error @ std::env::VarError::NotUnicode(_)) => {
            Err(error).with_context(|| format!("read environment variable {name}"))
        }
    }
}

#[cfg(test)]
mod tests {
    use std::path::Path;

    use clap::Parser;
    use paperstore::PaperNum;
    use paperstore_sqlite::SqliteBackend;
    use serde_json::json;
    use tempfile::TempDir;

    use super::{
        Cli, DEFAULT_PROMPT, detail_lines, gateway_origin, load_paper_md, prompt_name,
        selected_model,
    };

    fn paper_num() -> PaperNum {
        PaperNum::parse("P4003R2").unwrap_or_else(|e| panic!("parse: {e}"))
    }

    /// A temp-dir paper store with the schema ensured and rows inserted by
    /// hand, mirroring the fixture pattern in the paperstore-sqlite tests.
    struct StoreFixture {
        dir: TempDir,
    }

    impl StoreFixture {
        fn new() -> Self {
            let dir = TempDir::new().unwrap_or_else(|e| panic!("create temp dir: {e}"));
            Self { dir }
        }

        fn backend(&self) -> SqliteBackend {
            SqliteBackend::new(self.dir.path()).unwrap_or_else(|e| panic!("open backend: {e}"))
        }

        fn insert_row(&self, paper_id: &str, markdown_path: &str) {
            rusqlite::Connection::open(self.dir.path().join("paperstore.db"))
                .unwrap_or_else(|e| panic!("open raw connection: {e}"))
                .execute(
                    "INSERT INTO papers (paper_id, markdown_path) VALUES (?1, ?2)",
                    rusqlite::params![paper_id, markdown_path],
                )
                .unwrap_or_else(|e| panic!("insert row: {e}"));
        }
    }

    #[test]
    fn parser_accepts_a_paper_number_and_normalizes_case() {
        let cli = Cli::parse_from(["paperweight", "p4003r2"]);
        assert_eq!(cli.paper.as_str(), "P4003R2");
        assert_eq!(
            cli.output, None,
            "no --output means the report goes to stdout"
        );
        assert_eq!(cli.prompt, None);
        assert_eq!(cli.model, None);

        let cli = Cli::parse_from([
            "paperweight",
            "P4003R2",
            "--output",
            "out/analysis.md",
            "--prompt",
            "custom.md",
            "--model",
            "writer-model",
        ]);
        assert_eq!(cli.output.as_deref(), Some(Path::new("out/analysis.md")));
        assert_eq!(cli.prompt.as_deref(), Some(Path::new("custom.md")));
        assert_eq!(cli.model.as_deref(), Some("writer-model"));
    }

    #[test]
    fn parser_requires_a_paper_number() {
        assert!(Cli::try_parse_from(["paperweight"]).is_err());
    }

    #[test]
    fn parser_rejects_invalid_paper_numbers() {
        for args in [
            &["paperweight", "4003"][..],
            &["paperweight", "PR2"][..],
            &["paperweight", ""][..],
        ] {
            assert!(
                Cli::try_parse_from(args).is_err(),
                "a malformed paper number must be a usage error: {args:?}",
            );
        }
    }

    #[test]
    fn parser_rejects_unknown_flag_and_extras() {
        assert!(
            Cli::try_parse_from(["paperweight", "P4003R2", "N4950"]).is_err(),
            "clap must reject a trailing argument instead of silently dropping it",
        );
        assert!(Cli::try_parse_from(["paperweight", "--bogus", "P4003R2"]).is_err());
        for removed in ["--file", "--args"] {
            assert!(
                Cli::try_parse_from(["paperweight", "P4003R2", removed, "x"]).is_err(),
                "{removed} is no longer accepted",
            );
        }
    }

    #[test]
    fn verbose_flag_parses() {
        assert!(!Cli::parse_from(["paperweight", "P4003R2"]).verbose);
        assert!(Cli::parse_from(["paperweight", "P4003R2", "--verbose"]).verbose);
        assert!(Cli::parse_from(["paperweight", "P4003R2", "-v"]).verbose);
    }

    #[test]
    fn detail_lines_show_tool_calls_and_results() {
        let calls = json!({
            "kind": "assistant_tool_calls",
            "calls": [{ "id": "c1", "name": "search", "arguments": { "query": "Yihe Li" } }],
        });
        assert_eq!(
            detail_lines(&calls),
            [r#"    -> call c1 search {"query":"Yihe Li"}"#]
        );

        let result = json!({
            "kind": "tool_result",
            "tool_call_id": "c1",
            "alias": "search",
            "content": "status 401\nUnauthorized",
        });
        assert_eq!(
            detail_lines(&result),
            [
                "    <- result c1 search:",
                "        status 401",
                "        Unauthorized"
            ]
        );

        assert_eq!(
            detail_lines(&json!({ "kind": "lua", "message": "hi" })),
            ["    lua: hi"]
        );
        assert_eq!(
            detail_lines(&json!({ "kind": "tool_call_failed" })),
            Vec::<String>::new()
        );
    }

    #[test]
    fn selected_model_trims_or_defers() {
        assert_eq!(selected_model(None), None);
        assert_eq!(selected_model(Some("  ")), None);
        assert_eq!(selected_model(Some(" writer ")).as_deref(), Some("writer"));
    }

    #[test]
    fn gateway_origin_strips_v1() {
        for url in [
            "http://gw:8080",
            "http://gw:8080/",
            "http://gw:8080/v1",
            " http://gw:8080/v1/ ",
        ] {
            assert_eq!(gateway_origin(url), "http://gw:8080", "for {url:?}");
        }
    }

    #[test]
    fn embedded_prompt_declares_io() {
        assert!(DEFAULT_PROMPT.contains("\npromptforge: 0\n"));
        assert!(DEFAULT_PROMPT.contains("path: paper.md"));
        assert!(DEFAULT_PROMPT.contains("path: report.md"));
    }

    #[test]
    fn embedded_prompt_declares_weight_output_and_labels() {
        assert!(DEFAULT_PROMPT.contains("Weight: "));
        assert!(DEFAULT_PROMPT.contains("Weight: n/a"));
        assert!(DEFAULT_PROMPT.contains(r#"store.write("weight.md", weight_line)"#));
        assert!(DEFAULT_PROMPT.contains(r#"read_or_empty("weight.md")"#));
        assert!(DEFAULT_PROMPT.contains(r#"label = "Weightless""#));
        assert!(DEFAULT_PROMPT.contains(r#"label = "Light""#));
        assert!(DEFAULT_PROMPT.contains(r#"label = "Medium""#));
        assert!(DEFAULT_PROMPT.contains(r#"label = "Heavy""#));
        assert!(DEFAULT_PROMPT.contains(r#"label = "Supermassive""#));
        assert!(!DEFAULT_PROMPT.contains("Verdict: "));
        assert!(!DEFAULT_PROMPT.contains("verdict.md"));
    }

    #[test]
    fn store_input_loads_the_markdown_verbatim() {
        let fixture = StoreFixture::new();
        let backend = fixture.backend();
        let md = fixture.dir.path().join("p4003r2.md");
        let contents = "# Paper\n\nunicode \u{201c}quotes\u{201d} and trailing space \n\n";
        std::fs::write(&md, contents).unwrap_or_else(|e| panic!("write md: {e}"));
        fixture.insert_row("P4003R2", &md.to_string_lossy());

        let text = load_paper_md(&backend, &paper_num()).unwrap_or_else(|e| panic!("load: {e}"));

        assert_eq!(text, contents);
    }

    #[test]
    fn store_input_unknown_number_gives_missing_paper() {
        let fixture = StoreFixture::new();
        let backend = fixture.backend();

        let result = load_paper_md(&backend, &paper_num());

        // The variant is `#[non_exhaustive]`, so downstream code cannot name
        // it in a pattern; assert the Display contract instead.
        let error = match result {
            Err(error) => error,
            Ok(text) => panic!("expected an error, got {text:?}"),
        };
        assert_eq!(error.to_string(), "no metadata for paper P4003R2");
    }

    #[test]
    fn store_input_empty_markdown_path_gives_missing_markdown() {
        let fixture = StoreFixture::new();
        let backend = fixture.backend();
        fixture.insert_row("P4003R2", "");

        let result = load_paper_md(&backend, &paper_num());

        // The variant is `#[non_exhaustive]`, so downstream code cannot name
        // it in a pattern; assert the Display contract instead.
        let error = match result {
            Err(error) => error,
            Ok(text) => panic!("expected an error, got {text:?}"),
        };
        assert_eq!(error.to_string(), "no converted markdown for paper P4003R2");
    }

    #[test]
    fn prompt_name_uses_file_stem() {
        let name = |path: Option<&str>| prompt_name(path.map(Path::new));
        assert_eq!(name(None).ok().as_deref(), Some("paperweight"));
        assert_eq!(
            name(Some("/code/prompts/agora-author-advocacy.md"))
                .ok()
                .as_deref(),
            Some("agora-author-advocacy")
        );
        assert_eq!(name(Some("hello")).ok().as_deref(), Some("hello"));
        assert!(
            name(Some("/")).is_err(),
            "a path with no file name is refused"
        );
        assert!(name(Some("")).is_err(), "an empty path is refused");
    }
}
