//! Application orchestration for the CLI.
//!
//! `run_cli` owns the process boundary (argument parsing, signal installation,
//! exit status). This module owns everything between: it validates the gateway
//! environment and model selection, resolves the prompt source and its name
//! (the embedded paperweight prompt by default, `--prompt` from disk otherwise),
//! loads the paper markdown (from the SQLite paper store for a paper number,
//! verbatim from disk for `--file`), and runs the prompt as a harness session.
//! The harness stages the paper at the prompt's declared input and hands back
//! its declared output, which is written to `--output`, or to stdout when no
//! path is given.

use std::ffi::OsStr;
use std::fmt;
use std::io::{self, Write as _};
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use clap::Parser;
use harness::cancel::CancelHandle;
use harness::{
    CatalogBinding, FailureKind, GatewayBinding, Harness, HarnessConfig, HostSnapshot,
    LaunchRequest, OutputError, Session, SessionEvent, SessionState,
};
use paperstore::{PaperNum, StorageBackend};
use paperstore_sqlite::SqliteBackend;
use tokio::sync::broadcast::error::RecvError;

/// The embedded paperweight prompt, vendored from the promptforge prompts.
const DEFAULT_PROMPT: &str = include_str!("../paperweight.md");

/// The name the embedded prompt runs under.
const DEFAULT_PROMPT_NAME: &str = "paperweight";

/// The command-line interface; `run_cli` sets the program name.
#[derive(Debug, Parser)]
#[command(
    version,
    about = "Run a promptforge prompt against a WG21 paper",
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
    /// The cooperative cancellation handle wired to Ctrl-C.
    pub(crate) cancel: CancelHandle,
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
/// Returns an error if either gateway variable is unset or blank, the paper
/// input cannot be loaded (`WG21_DATA_DIR` unset, the number missing from the
/// store or without converted markdown, or the `--file` path unreadable), the
/// gateway model list cannot be fetched or lists no chat model, the harness
/// refuses the launch (including a selected model the gateway does not list),
/// the run fails,
/// the run is cancelled ([`Cancelled`]), or the prompt did not produce its
/// declared output, or the `--prompt` path has no usable file name.
pub(crate) async fn run(request: RunRequest<'_>) -> Result<()> {
    let RunRequest {
        input,
        output,
        prompt,
        model,
        args,
        cancel,
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
    // Load before the launch: a store miss or an unreadable file fails fast,
    // before any network call.
    let paper_md = load_input_markdown(input).await?;
    let models = fetch_chat_models(&base_url, &key).await?;
    if models.is_empty() {
        bail!("the gateway at {base_url} lists no chat model");
    }

    // Removed when `work` drops, whether or not the run succeeds.
    let work = tempfile::Builder::new()
        .prefix(&format!("{name}-"))
        .tempdir()
        .context("create the run's scratch directory")?;
    let agents_path = work.path().join("agents");
    let state_dir = work.path().join("state");
    for dir in [&agents_path, &state_dir] {
        tokio::fs::create_dir_all(dir)
            .await
            .with_context(|| format!("create directory {}", dir.display()))?;
    }
    let prompt_path = agents_path.join(format!("{name}.md"));
    tokio::fs::write(&prompt_path, &source)
        .await
        .with_context(|| format!("write the prompt to {}", prompt_path.display()))?;

    let harness = Harness::new(HarnessConfig {
        agents_path,
        state_dir,
    });
    harness.set_gateway(GatewayBinding {
        base_url,
        key,
        generation: 1,
    });
    harness.set_catalog(CatalogBinding {
        generation: 1,
        models,
    });
    harness.set_host(HostSnapshot {
        selected_model: model,
        workspace_roots: Vec::new(),
    });

    let session = harness
        .launch(LaunchRequest {
            agent: name.clone(),
            args: args.to_owned(),
            input_text: Some(paper_md),
        })
        .await
        .with_context(|| format!("launch the {name} session"))?;
    let ending = await_closed(&session, &cancel).await;

    let report = match session.output_text() {
        Ok(report) => report,
        Err(OutputError::Unfinished) if ending.cancelled => return Err(Cancelled.into()),
        Err(OutputError::Unfinished) => match ending.failure {
            Some(message) => bail!("run failed: {message}"),
            None => bail!("run did not complete"),
        },
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

/// How a session ended, as the CLI observed it.
#[derive(Debug, Default)]
struct Ending {
    /// Ctrl-C requested the close.
    cancelled: bool,
    /// The last run-failure report, when the run ended in error.
    failure: Option<String>,
}

/// Prints the session's progress to stderr until it reports `Closed`,
/// closing it for good when `cancel` fires.
///
/// A session closes on its own when its run completes or fails, so this
/// returns without a Ctrl-C too.
async fn await_closed(session: &Session, cancel: &CancelHandle) -> Ending {
    let mut events = session.subscribe_events();
    let mut errors = session.subscribe_errors();
    let mut state = session.subscribe_state();
    let mut ending = Ending::default();
    let mut events_open = true;
    let mut errors_open = true;
    loop {
        if *state.borrow_and_update() == SessionState::Closed {
            break;
        }
        tokio::select! {
            changed = state.changed() => {
                if changed.is_err() {
                    break;
                }
            }
            event = events.recv(), if events_open => match event {
                Ok(event) => print_progress(&event),
                Err(RecvError::Lagged(_)) => {}
                Err(RecvError::Closed) => events_open = false,
            },
            failure = errors.recv(), if errors_open => match failure {
                Ok(failure) if failure.kind == FailureKind::RunFailed => {
                    ending.failure = Some(failure.message);
                }
                Ok(_) | Err(RecvError::Lagged(_)) => {}
                Err(RecvError::Closed) => errors_open = false,
            },
            () = cancel.cancelled(), if !ending.cancelled => {
                ending.cancelled = true;
                session.close();
            }
        }
    }
    // A failure reported alongside the close may still be queued.
    while let Ok(failure) = errors.try_recv() {
        if failure.kind == FailureKind::RunFailed {
            ending.failure = Some(failure.message);
        }
    }
    ending
}

/// Writes one progress line for a session event to stderr.
fn print_progress(event: &SessionEvent) {
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

/// Returns the string field `name` of the event's payload, or `-`.
fn event_field<'a>(event: &'a SessionEvent, name: &str) -> &'a str {
    let Some(value) = event.event.get(name) else {
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
/// A missing or blank selection is `None`, which the harness resolves to the
/// first model in the catalog binding.
fn selected_model(model: Option<&str>) -> Option<String> {
    model
        .map(str::trim)
        .filter(|model| !model.is_empty())
        .map(str::to_owned)
}

/// Fetches the gateway's model list and returns its chat-capable entries,
/// in the gateway's order.
async fn fetch_chat_models(base_url: &str, key: &str) -> Result<Vec<serde_json::Value>> {
    let url = format!("{base_url}/v1/models");
    let list: serde_json::Value = reqwest::Client::new()
        .get(&url)
        .bearer_auth(key)
        .send()
        .await
        .and_then(reqwest::Response::error_for_status)
        .with_context(|| format!("fetch the gateway model list from {url}"))?
        .json()
        .await
        .with_context(|| format!("decode the gateway model list from {url}"))?;
    chat_models(list).with_context(|| format!("read the gateway model list from {url}"))
}

/// Returns the chat-capable entries of an OpenAI-shape model list.
///
/// An entry is chat-capable when it has a non-empty `id` and either no
/// `kind` or `kind` `"chat"`, the rule the promptforge workshop applies.
fn chat_models(list: serde_json::Value) -> Result<Vec<serde_json::Value>> {
    let serde_json::Value::Object(mut list) = list else {
        bail!("the model list is not a JSON object");
    };
    let Some(serde_json::Value::Array(models)) = list.remove("data") else {
        bail!("the model list has no `data` array");
    };
    Ok(models.into_iter().filter(is_chat_capable).collect())
}

/// Returns whether `model` is a chat model with a usable id.
fn is_chat_capable(model: &serde_json::Value) -> bool {
    let has_id = model
        .get("id")
        .and_then(serde_json::Value::as_str)
        .is_some_and(|id| !id.is_empty());
    let chat_kind = match model.get("kind") {
        None => true,
        Some(serde_json::Value::String(kind)) => kind == "chat",
        Some(_) => false,
    };
    has_id && chat_kind
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
        Cli, DEFAULT_PROMPT, PaperInput, chat_models, gateway_origin, load_input_markdown,
        load_paper_md, prompt_name, selected_model,
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
    fn chat_models_filters_non_chat() {
        let list = json!({ "object": "list", "data": [
            { "id": "whisper-base", "kind": "transcription" },
            { "id": "analyst", "kind": "chat" },
            { "id": "" },
            { "id": "plain" },
            { "id": "odd", "kind": 3 },
        ]});
        let models = chat_models(list).unwrap_or_else(|e| panic!("chat models: {e}"));
        assert_eq!(
            models,
            [
                json!({ "id": "analyst", "kind": "chat" }),
                json!({ "id": "plain" })
            ]
        );
    }

    #[test]
    fn chat_models_rejects_missing_data() {
        assert!(chat_models(json!({ "object": "list" })).is_err());
        assert!(chat_models(json!([])).is_err());
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
