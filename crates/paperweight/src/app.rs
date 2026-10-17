//! Application orchestration for the CLI.
//!
//! `run_cli` owns the process boundary (argument parsing, signal installation,
//! exit status). This module owns everything between: it validates the gateway
//! environment and model selection, resolves the prompt source and its name
//! (the embedded paperweight prompt by default, `--prompt` from disk otherwise),
//! loads the paper markdown (from the SQLite paper store for a paper number,
//! verbatim from disk for `--file`), and runs the prompt through one harness
//! run whose model rounds go to the gateway. The harness stages the paper at
//! the prompt's declared input and hands back its declared output, which is
//! written to `--output`, or to stdout when no path is given.

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
use harness::{BoxFuture, Harness, HostSnapshot, OutputError, Timer};
use harness_gateway_client::{GatewayBroker, GatewayEndpoint, SecretString};
use paperstore::{PaperNum, StorageBackend};
use paperstore_sqlite::SqliteBackend;
use tokio::sync::oneshot;

/// The embedded paperweight prompt, vendored from the runvil prompts.
const DEFAULT_PROMPT: &str = include_str!("../paperweight.md");

/// The name the embedded prompt runs under.
const DEFAULT_PROMPT_NAME: &str = "paperweight";

/// The command-line interface; `run_cli` sets the program name.
#[derive(Debug, Parser)]
#[command(
    version,
    about = "Run a runvil prompt against a WG21 paper",
    group = clap::ArgGroup::new("input").args(["paper", "file"]).required(true)
)]
pub(crate) struct Cli {
    /// The WG21 paper number to analyze, resolved through the paper store.
    pub(crate) paper: Option<PaperNum>,
    /// Analyze the paper markdown file at PATH instead of a store lookup.
    #[arg(long, value_name = "PATH")]
    pub(crate) file: Option<PathBuf>,
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
    /// The prompt's arguments, passed verbatim: a JSON object for a prompt
    /// that declares `args:`, or plain text.
    #[arg(long, value_name = "TEXT", default_value = "")]
    pub(crate) args: String,
}

impl Cli {
    /// Returns the selected paper input.
    ///
    /// The `input` arg group rejects the both/neither states as usage errors
    /// at parse time, so they cannot occur here.
    pub(crate) fn input(&self) -> PaperInput {
        match (&self.paper, &self.file) {
            (Some(num), None) => PaperInput::Number(num.clone()),
            (None, Some(path)) => PaperInput::File(path.clone()),
            _ => unreachable!("the `input` group requires exactly one of PAPER_NUM or --file"),
        }
    }
}

/// The paper to analyze: exactly one source per run.
///
/// The clap `input` group enforces the invariant at parse time; this type
/// carries it, so no downstream code can observe a both/neither state.
#[derive(Debug)]
pub(crate) enum PaperInput {
    /// A paper number resolved through the SQLite-backed paper store.
    Number(PaperNum),
    /// A markdown file read verbatim from disk.
    File(PathBuf),
}

/// A single analysis run: what to read, where to write, and cancellation.
pub(crate) struct RunRequest<'a> {
    /// The paper input to analyze.
    pub(crate) input: &'a PaperInput,
    /// Where the analysis report is written; stdout when `None`.
    pub(crate) output: Option<&'a Path>,
    /// An optional prompt file overriding the embedded default.
    pub(crate) prompt: Option<&'a Path>,
    /// The gateway model id to bind; `None` binds the gateway's first chat
    /// model.
    pub(crate) model: Option<&'a str>,
    /// The prompt's arguments, passed verbatim.
    pub(crate) args: &'a str,
    /// Resolves once when Ctrl-C asks the run to end.
    pub(crate) cancel: oneshot::Receiver<()>,
}

impl std::fmt::Debug for RunRequest<'_> {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("RunRequest")
            .field("input", &self.input)
            .field("output", &self.output)
            .field("prompt", &self.prompt)
            .field("model", &self.model)
            .field("args", &self.args)
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
/// Returns an error if either gateway variable is unset, blank, or not a
/// usable gateway URL or key, the paper input cannot be loaded
/// (`WG21_DATA_DIR` unset, the number missing from the store or without
/// converted markdown, or the `--file` path unreadable), the harness cannot
/// resolve the run's model (the gateway model list cannot be fetched, lists
/// no model, or lacks the selected one), the run fails, the run is cancelled
/// ([`Cancelled`]), the prompt did not produce its declared output, or the
/// `--prompt` path has no usable file name.
pub(crate) async fn run(request: RunRequest<'_>) -> Result<()> {
    let RunRequest {
        input,
        output,
        prompt,
        model,
        args,
        mut cancel,
    } = request;
    let name = prompt_name(prompt)?;
    let (base_url, key) = gateway_from_env(&name)?;
    let endpoint = GatewayEndpoint::new(&format!("{base_url}/v1"))
        .with_context(|| format!("use the gateway at {base_url}"))?;
    let key = SecretString::new(key).context("use the gateway API key")?;
    let model = selected_model(model);

    let source = match prompt {
        Some(path) => tokio::fs::read_to_string(path)
            .await
            .with_context(|| format!("read prompt file {}", path.display()))?,
        None => DEFAULT_PROMPT.to_owned(),
    };
    // Load before the run: a store miss or an unreadable file fails fast,
    // before any network call.
    let paper_md = load_input_markdown(input).await?;

    let harness = Harness::new(
        Arc::new(ProgressRecorder),
        Arc::new(GatewayBroker::new(endpoint, key)),
        Arc::new(TokioTimer),
        Arc::new(HostContext::new(
            PackageRegistry::new(),
            HostServices::new(),
        )),
        HostServices::new(),
    );
    let control = harness.control();
    let run = harness.run(harness::RunRequest {
        name: name.clone(),
        source,
        args: args.to_owned(),
        input_text: Some(paper_md),
        vfs: VfsRef::default(),
        host: HostSnapshot {
            selected_model: model,
            workspace_roots: Vec::new(),
        },
    });
    tokio::pin!(run);
    let mut cancel_requested = false;
    // A failed Ctrl-C listener drops the sender; the pattern then disables
    // the branch and the run goes on uncancellable.
    let report = loop {
        tokio::select! {
            result = &mut run => break result,
            Ok(()) = &mut cancel, if !cancel_requested => {
                cancel_requested = true;
                control.cancel();
            }
        }
    }
    .with_context(|| format!("run the {name} prompt"))?;

    match report.outcome {
        RunOutcome::Completed { .. } => {}
        RunOutcome::Cancelled => return Err(Cancelled.into()),
        RunOutcome::Failed { message, .. } => bail!("run failed: {message}"),
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

/// The run's recorder: prints one progress line to stderr for each event
/// and keeps no history, since the CLI reads the run's result from its
/// report.
#[derive(Debug)]
struct ProgressRecorder;

impl RunRecorder for ProgressRecorder {
    fn begin_run(&self, _meta: RunMeta) -> RecorderFuture<'_, RunId> {
        Box::pin(async { Ok(RunId::from_raw(1)) })
    }

    fn append(&self, _run: RunId, record: Record) -> RecorderFuture<'_, ()> {
        if matches!(record.kind, RecordKind::Event) {
            print_progress(&record.payload);
        }
        Box::pin(async { Ok(()) })
    }

    fn end_run(&self, _run: RunId, _outcome: RunOutcome) -> RecorderFuture<'_, ()> {
        Box::pin(async { Ok(()) })
    }
}

/// Sleeps on the CLI runtime's tokio timer.
#[derive(Debug)]
struct TokioTimer;

impl Timer for TokioTimer {
    fn sleep(&self, duration: Duration) -> BoxFuture<()> {
        Box::pin(tokio::time::sleep(duration))
    }
}

/// Writes one progress line for a run event to stderr.
fn print_progress(event: &serde_json::Value) {
    // Progress is a side channel, so a failed write to stderr is
    // deliberately dropped rather than surfaced.
    let _ignored = writeln!(
        io::stderr(),
        "[{}] {}: {}",
        event_field(event, "execution"),
        event_field(event, "section"),
        event_field(event, "kind"),
    );
}

/// Returns the string field `name` of the event, or `-`.
fn event_field<'a>(event: &'a serde_json::Value, name: &str) -> &'a str {
    let Some(value) = event.get(name) else {
        return "-";
    };
    value.as_str().unwrap_or("-")
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

/// Loads the paper markdown for the selected input.
///
/// The store branch is synchronous: one indexed SQLite lookup plus one file
/// read, matching the Python tool, and trivial next to the model calls that
/// follow. The `File` branch never touches `WG21_DATA_DIR`.
async fn load_input_markdown(input: &PaperInput) -> Result<String> {
    match input {
        PaperInput::Number(num) => {
            let backend = SqliteBackend::from_env()?;
            Ok(load_paper_md(&backend, num)?)
        }
        PaperInput::File(path) => tokio::fs::read_to_string(path)
            .await
            .with_context(|| format!("read paper file {}", path.display())),
    }
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
/// A missing or blank selection is `None`, which the harness resolves
/// against the gateway's model list.
fn selected_model(model: Option<&str>) -> Option<String> {
    model
        .map(str::trim)
        .filter(|model| !model.is_empty())
        .map(str::to_owned)
}

/// Returns the name the run takes from its prompt: the `--prompt` file stem,
/// or [`DEFAULT_PROMPT_NAME`] for the embedded prompt.
///
/// The name becomes the run's `execution` field in every progress line.
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
    let endpoint = env_optional("RUNVIL_GATEWAY_URL")?;
    let token = env_optional("RUNVIL_GATEWAY_API_KEY")?;
    let endpoint = endpoint.map(|value| gateway_origin(&value));
    let token = token.map(|value| value.trim().to_owned());
    match (endpoint, token) {
        (Some(endpoint), Some(token)) if !endpoint.is_empty() && !token.is_empty() => {
            Ok((endpoint, token))
        }
        _ => bail!(
            "RUNVIL_GATEWAY_URL and RUNVIL_GATEWAY_API_KEY must both be set: \
             the {name} prompt binds its models through the gateway"
        ),
    }
}

/// Returns the gateway origin for `url`: trimmed, without trailing slashes
/// or a `/v1` suffix, because `run` appends `/v1` itself.
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
    use tempfile::TempDir;

    use super::{
        Cli, DEFAULT_PROMPT, PaperInput, gateway_origin, load_input_markdown, load_paper_md,
        prompt_name, selected_model,
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
        assert_eq!(cli.paper.as_ref().map(PaperNum::as_str), Some("P4003R2"));
        assert_eq!(cli.file, None);
        assert_eq!(
            cli.output, None,
            "no --output means the report goes to stdout"
        );
        assert_eq!(cli.prompt, None);
        assert_eq!(cli.args, "", "no --args launches with empty arguments");

        let cli = Cli::parse_from([
            "paperweight",
            "P4003R2",
            "--output",
            "out/analysis.md",
            "--prompt",
            "custom.md",
            "--model",
            "writer-model",
            "--args",
            r#"{"id": "P4003R2"}"#,
        ]);
        assert_eq!(cli.args, r#"{"id": "P4003R2"}"#);
        assert_eq!(cli.output.as_deref(), Some(Path::new("out/analysis.md")));
        assert_eq!(cli.prompt.as_deref(), Some(Path::new("custom.md")));
        assert_eq!(cli.model.as_deref(), Some("writer-model"));
    }

    #[test]
    fn parser_accepts_file_alone() {
        let cli = Cli::parse_from(["paperweight", "--file", "paper.md"]);
        assert_eq!(cli.paper, None);
        assert_eq!(cli.file.as_deref(), Some(Path::new("paper.md")));
    }

    #[test]
    fn parser_rejects_both_inputs_and_neither() {
        assert!(
            Cli::try_parse_from(["paperweight", "P4003R2", "--file", "paper.md"]).is_err(),
            "the input group must reject a number together with --file",
        );
        assert!(
            Cli::try_parse_from(["paperweight"]).is_err(),
            "the input group must require exactly one input",
        );
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
    }

    #[test]
    fn selected_model_trims_or_defers() {
        assert_eq!(selected_model(None), None);
        assert_eq!(selected_model(Some("  ")), None);
        assert_eq!(selected_model(Some(" writer ")).as_deref(), Some("writer"));
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
        assert!(DEFAULT_PROMPT.contains("\nrunvil: 0\n"));
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

    #[tokio::test]
    async fn file_input_reads_the_file_verbatim() {
        let dir = TempDir::new().unwrap_or_else(|e| panic!("create temp dir: {e}"));
        let path = dir.path().join("paper.md");
        let contents = "# Paper\n\nunicode \u{201c}quotes\u{201d} and trailing space \n\n";
        std::fs::write(&path, contents).unwrap_or_else(|e| panic!("write paper: {e}"));

        let text = load_input_markdown(&PaperInput::File(path))
            .await
            .unwrap_or_else(|e| panic!("load: {e}"));

        assert_eq!(text, contents);
    }
}
