//! Application orchestration for the `papergate` CLI.
//!
//! `main` owns the process boundary (argument parsing, signal installation,
//! exit status). This module owns everything between: it validates the gateway
//! environment, resolves the prompt source (the embedded prompt by default,
//! `--prompt` from disk otherwise), loads the paper markdown (from the SQLite
//! paper store for a paper number, verbatim from disk for `--file`), stands
//! up a one-shot promptforge harness over a per-run scratch directory, binds
//! the gateway and the one model the prompt's `writer` role fills from,
//! launches the prompt as a harness agent session with the paper as the run's
//! `args`, follows the session to its close, and writes the report to
//! `--output`, or to stdout when no path is given.
//!
//! The harness (`harness-api`) is the engine's production host: it owns the
//! tokio effect loop, the gateway transport, the run log, and the run's
//! store. papergate never touches the engine directly. The harness exposes a
//! run's outcome as session state and events, not as a value, so the report
//! is the run's last assistant reply: the prompt's final section ends with
//! the model call that writes it.

use std::path::{Path, PathBuf};
use std::time::Duration;

use anyhow::{Context, Result, bail};
use clap::Parser;
use harness_api::cancel::CancelHandle;
use harness_api::{
    CatalogBinding, FailureKind, GatewayBinding, Harness, HarnessConfig, HostSnapshot,
    LaunchRequest, Session, SessionEvent, SessionFailure, SessionState,
};
use paperstore::{PaperNum, StorageBackend};
use paperstore_sqlite::SqliteBackend;
use tokio::sync::broadcast::error::RecvError;

/// The embedded papergate prompt.
const DEFAULT_PROMPT: &str = include_str!("../papergate.md");

/// The gateway model the prompt's `writer` role binds to unless `--model`
/// or `PAPERGATE_MODEL` names another. The capability-named catalog entry
/// every C++ Alliance gateway serves.
const DEFAULT_MODEL: &str = "reasoning-large";

/// The agent name the harness discovers the prompt under: it is written as
/// `<AGENT>.md` into the run's agents directory and launched by this name.
const AGENT: &str = "papergate";

/// The generation papergate assigns its gateway and catalog bindings. The
/// harness rebuilds its resources when a generation changes; a one-shot run
/// pushes exactly one of each.
const BINDING_GENERATION: u64 = 1;

/// The OpenAI-compatible API root suffix the harness appends to the gateway
/// base URL itself (`GatewayBinding::api_root`).
const GATEWAY_API_SUFFIX: &str = "/v1";

/// Event kinds the progress feed does not echo: the raw model-turn bodies,
/// present only in debug runs and bulky when they are.
const SILENT_EVENT_KINDS: &[&str] = &["request", "response"];

/// How long a run that ended without success is given for its failure
/// report to land. The harness flips the session state to `Closed` before it
/// broadcasts the report, so a client that stopped listening at `Closed`
/// would lose the reason. The report is sent in the same synchronous stretch
/// as the state change, so this bounds scheduling, not a wait the run fills.
const FAILURE_REPORT_GRACE: Duration = Duration::from_secs(2);

/// The `papergate` command-line interface.
#[derive(Debug, Parser)]
#[command(
    name = "papergate",
    version,
    about = "Report on the evidence a WG21 paper provides for its need of standardization",
    group = clap::ArgGroup::new("input").args(["paper", "file"]).required(true)
)]
pub(crate) struct Cli {
    /// The WG21 paper number to analyze, resolved through the paper store.
    pub(crate) paper: Option<PaperNum>,
    /// Analyze the paper markdown file at PATH instead of a store lookup.
    #[arg(long, value_name = "PATH")]
    pub(crate) file: Option<PathBuf>,
    /// Write the analysis report to PATH instead of stdout.
    #[arg(long, value_name = "PATH")]
    pub(crate) output: Option<PathBuf>,
    /// Read the prompt from PATH instead of the embedded papergate prompt.
    #[arg(long, value_name = "PATH")]
    pub(crate) prompt: Option<PathBuf>,
    /// The gateway model the prompt's writer role binds to.
    #[arg(long, value_name = "NAME", env = "PAPERGATE_MODEL", default_value = DEFAULT_MODEL)]
    pub(crate) model: String,
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

/// A single analysis run: what to read, where to write, which model, and
/// cancellation.
pub(crate) struct RunRequest<'a> {
    /// The paper input to analyze.
    pub(crate) input: &'a PaperInput,
    /// Where the analysis report is written; stdout when `None`.
    pub(crate) output: Option<&'a Path>,
    /// An optional prompt file overriding the embedded default.
    pub(crate) prompt: Option<&'a Path>,
    /// The gateway model name the prompt's declared role binds to.
    pub(crate) model: &'a str,
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
            .finish_non_exhaustive()
    }
}

/// The run was cancelled cooperatively (Ctrl-C) before it produced a report.
///
/// The harness reports a requested close as session state, not as an error;
/// this type carries it through the `anyhow` chain so `main` can select exit
/// code 130.
#[derive(Debug)]
pub(crate) struct Cancelled;

impl std::fmt::Display for Cancelled {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str("the run was cancelled")
    }
}

impl std::error::Error for Cancelled {}

/// Runs one analysis using the gateway configuration read from the environment.
///
/// # Errors
/// Returns an error if either gateway variable is unset or blank, the paper
/// input cannot be loaded (`WG21_DATA_DIR` unset, the number missing from the
/// store or without converted markdown, or the `--file` path unreadable), the
/// prompt file cannot be read, the harness refuses the launch, the session
/// reports a failure (the prompt does not parse, the gateway does not serve
/// the model, the model falls short of the prompt's requirements, or a model
/// round fails), the run is cancelled ([`Cancelled`]), or the run ends
/// without a report.
pub(crate) async fn run(request: RunRequest<'_>) -> Result<()> {
    let RunRequest {
        input,
        output,
        prompt,
        model,
        cancel,
    } = request;
    let gateway = gateway_from_env()?;

    let source = match prompt {
        Some(path) => tokio::fs::read_to_string(path)
            .await
            .with_context(|| format!("read prompt file {}", path.display()))?,
        None => DEFAULT_PROMPT.to_owned(),
    };

    // Load before the harness stands up: a store miss or an unreadable file
    // fails fast, before any network call.
    let paper_md = load_input_markdown(input).await?;

    let run_dir = std::env::temp_dir().join(format!(
        "papergate-{:016x}{:016x}",
        fastrand::u64(..),
        fastrand::u64(..)
    ));
    let launch = Launch {
        run_dir: &run_dir,
        source: &source,
        gateway,
        model,
        paper_md,
        cancel,
    };
    let result = run_session(launch).await;
    // Best-effort: the scratch directory holds the agent file and the
    // harness's run log, and a cleanup failure must not mask the run's own
    // outcome.
    let _ignored = std::fs::remove_dir_all(&run_dir);
    let report = result?;

    match output {
        Some(path) => {
            std::fs::write(path, &report)
                .with_context(|| format!("write the report to {}", path.display()))?;
            println!("{}", path.display());
        }
        None => write_stdout(report.as_bytes())?,
    }
    Ok(())
}

/// Everything one harness session needs beyond the environment.
struct Launch<'a> {
    /// The per-run scratch directory: the agents directory and the
    /// harness's state directory live under it.
    run_dir: &'a Path,
    /// The prompt source, written as the agent file.
    source: &'a str,
    /// The gateway the harness binds.
    gateway: GatewayEnv,
    /// The gateway model the prompt's declared role binds to.
    model: &'a str,
    /// The paper markdown, handed to the run as its `args`.
    paper_md: String,
    /// The cooperative cancellation handle wired to Ctrl-C.
    cancel: CancelHandle,
}

/// Stands up a harness over the scratch directory, launches the prompt as an
/// agent session with the paper as its `args`, and follows the session to
/// its close, returning the report.
async fn run_session(launch: Launch<'_>) -> Result<String> {
    let Launch {
        run_dir,
        source,
        gateway,
        model,
        paper_md,
        cancel,
    } = launch;
    let agents_path = run_dir.join("agents");
    tokio::fs::create_dir_all(&agents_path)
        .await
        .with_context(|| format!("create the agents directory {}", agents_path.display()))?;
    let agent_file = agents_path.join(format!("{AGENT}.md"));
    tokio::fs::write(&agent_file, source)
        .await
        .with_context(|| format!("write the agent file {}", agent_file.display()))?;

    let harness = Harness::new(HarnessConfig {
        agents_path,
        state_dir: run_dir.join("state"),
    });
    harness.set_gateway(GatewayBinding {
        base_url: gateway.base_url,
        key: gateway.key,
        generation: BINDING_GENERATION,
    });
    // The host snapshot's selection is the model every declared role fills
    // from; the harness resolves it against the gateway's live catalog at
    // launch and fails the run when the gateway does not serve it.
    harness.set_host(HostSnapshot {
        selected_model: Some(model.to_owned()),
        workspace_roots: Vec::new(),
    });
    harness.set_catalog(catalog_binding(model));

    let session = harness
        .launch(LaunchRequest {
            agent: AGENT.to_owned(),
            args: paper_md,
        })
        .await
        .context("launch the papergate agent session")?;
    follow_session(&harness, &session, cancel).await
}

/// Follows a launched session to its close: echoes its events as progress
/// lines, collects its failure reports, closes it on cancellation, and
/// returns the report once it is closed.
async fn follow_session(
    harness: &Harness,
    session: &Session,
    cancel: CancelHandle,
) -> Result<String> {
    // Subscribe before the backfill: nothing between the two is lost, and a
    // live event the backfill already covered is skipped by its index.
    let mut events = session.subscribe_events();
    let mut errors = session.subscribe_errors();
    let mut state = session.subscribe_state();
    let mut progress = Progress::default();
    absorb_transcript(session, &mut progress).await?;
    let mut closing = false;
    while *state.borrow_and_update() != SessionState::Closed {
        tokio::select! {
            biased;
            received = events.recv() => match received {
                Ok(event) => show(progress.absorb(&event)),
                // A lagged receiver lost live events; the transcript is the
                // durable copy and the cursor says where to resume.
                Err(RecvError::Lagged(_)) => absorb_transcript(session, &mut progress).await?,
                Err(RecvError::Closed) => break,
            },
            received = errors.recv() => match received {
                Ok(failure) => progress.fail(failure),
                // Reports are ephemeral; a lagged receiver missed a report
                // of a failure the state watch still ends the loop on.
                Err(RecvError::Lagged(_)) => {}
                Err(RecvError::Closed) => break,
            },
            changed = state.changed() => {
                if changed.is_err() {
                    break;
                }
            }
            () = cancel.cancelled(), if !closing => {
                closing = true;
                progress.cancelled = true;
                // Close, not cancel: a turn-cancel relaunches the program
                // over the retained transcript; close ends the session for
                // good and drains its outstanding effects.
                let _was_running = harness.close(session.id());
            }
        }
    }
    // The log is written before each live broadcast, so a read past the
    // cursor closes any gap between the last events and the close.
    absorb_transcript(session, &mut progress).await?;
    // The failure report, when the run needs one, may still be on its way:
    // the state reaches `Closed` ahead of it.
    if !progress.succeeded
        && progress.failures.is_empty()
        && let Ok(Ok(failure)) = tokio::time::timeout(FAILURE_REPORT_GRACE, errors.recv()).await
    {
        progress.fail(failure);
    }
    while let Ok(failure) = errors.try_recv() {
        progress.fail(failure);
    }
    progress.report()
}

/// Reads the transcript past the progress cursor and absorbs it.
async fn absorb_transcript(session: &Session, progress: &mut Progress) -> Result<()> {
    let backlog = session
        .transcript(progress.cursor)
        .await
        .context("read the session transcript")?;
    for event in &backlog {
        show(progress.absorb(event));
    }
    Ok(())
}

/// Writes one progress line to stderr, when there is one.
///
/// Progress is a side channel, so a failed write to stderr is deliberately
/// dropped rather than surfaced.
fn show(line: Option<String>) {
    if let Some(line) = line {
        eprintln!("{line}");
    }
}

/// What papergate has learned from a session's event stream: how far it has
/// read, the run's last assistant reply, and how the run ended.
#[derive(Debug, Default)]
struct Progress {
    /// The next transcript index to take; events below it were absorbed.
    cursor: u64,
    /// The text of the last `assistant_reply` event seen: the report, once
    /// the run has succeeded.
    last_reply: Option<String>,
    /// Whether a `run_succeeded` event was seen.
    succeeded: bool,
    /// The failures the session reported, in order.
    failures: Vec<SessionFailure>,
    /// Whether papergate itself asked the session to close (Ctrl-C).
    cancelled: bool,
}

impl Progress {
    /// Absorbs one event, returning the progress line to show for it, or
    /// `None` when the event was already absorbed (a live event the
    /// transcript backfill covered) or is one of the silent kinds.
    fn absorb(&mut self, event: &SessionEvent) -> Option<String> {
        if event.index < self.cursor {
            return None;
        }
        self.cursor = event.index + 1;
        let kind = field(&event.event, "kind").unwrap_or("unknown");
        match kind {
            "assistant_reply" => {
                if let Some(text) = field(&event.event, "text") {
                    self.last_reply = Some(text.to_owned());
                }
            }
            "run_succeeded" => self.succeeded = true,
            _ => {}
        }
        if SILENT_EVENT_KINDS.contains(&kind) {
            return None;
        }
        let section = field(&event.event, "section").unwrap_or("");
        Some(format!("[{AGENT}] {section}: {kind}"))
    }

    /// Records one failure the session reported.
    fn fail(&mut self, failure: SessionFailure) {
        self.failures.push(failure);
    }

    /// The report, once the session has closed.
    ///
    /// # Errors
    /// Returns [`Cancelled`] when papergate closed the session itself, the
    /// session's failure reports when it reported any, an error when the
    /// run never reported success, and an error when it succeeded without
    /// an assistant reply to serve as the report.
    fn report(self) -> Result<String> {
        if self.cancelled {
            return Err(Cancelled.into());
        }
        if !self.failures.is_empty() {
            let messages: Vec<String> = self
                .failures
                .iter()
                .map(|failure| format!("{}: {}", failure_label(failure.kind), failure.message))
                .collect();
            bail!("the papergate run failed: {}", messages.join("; "));
        }
        if !self.succeeded {
            bail!("the session closed without the run reporting success");
        }
        match self.last_reply {
            Some(report) => Ok(report),
            None => bail!(
                "the run succeeded without an assistant reply to report: the prompt's final \
                 section must end with the model call that writes the report"
            ),
        }
    }
}

/// One string field of an event's persisted JSON shape.
fn field<'a>(event: &'a serde_json::Value, name: &str) -> Option<&'a str> {
    event.get(name).and_then(serde_json::Value::as_str)
}

/// The label for one failure kind. The match is exhaustive on purpose: a
/// new kind fails this build until it is labelled here.
fn failure_label(kind: FailureKind) -> &'static str {
    match kind {
        FailureKind::ModelTurnFailed => "model turn failed",
        FailureKind::ToolCallFailed => "tool call failed",
        FailureKind::RunFailed => "run failed",
        FailureKind::Interrupted => "interrupted",
    }
}

/// The chat catalog binding the harness gates launches on.
///
/// The harness holds a launched session until a catalog with at least one
/// chat-capable entry is bound (in the Workshop, the model dropdown's list),
/// and resolves the selected model against the gateway's live catalog at
/// launch, failing the run when the gateway does not serve it. papergate has
/// exactly one model in play, so its catalog is that one entry; the harness's
/// own fetch is what validates the name.
fn catalog_binding(model: &str) -> CatalogBinding {
    CatalogBinding {
        generation: BINDING_GENERATION,
        models: vec![serde_json::json!({ "id": model })],
    }
}

/// Writes bytes to stdout verbatim, flushing before return.
///
/// Verbatim (no added newline) keeps the output pipe-friendly; the explicit
/// flush guarantees delivery before the process exits.
fn write_stdout(bytes: &[u8]) -> Result<()> {
    use std::io::Write as _;
    let mut stdout = std::io::stdout().lock();
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

/// The gateway as the harness binds it: its base URL and bearer key.
struct GatewayEnv {
    base_url: String,
    key: String,
}

/// Reads the gateway environment, requiring both variables.
///
/// The prompt binds its `writer` role through the gateway, so there is no
/// local-only mode: a missing credential is a startup error naming both
/// variables rather than a silent downgrade.
fn gateway_from_env() -> Result<GatewayEnv> {
    let endpoint = env_optional("PROMPTFORGE_GATEWAY_URL")?;
    let token = env_optional("PROMPTFORGE_GATEWAY_API_KEY")?;
    let endpoint = endpoint.map(|value| value.trim().to_owned());
    let token = token.map(|value| value.trim().to_owned());
    match (endpoint, token) {
        (Some(endpoint), Some(token)) if !endpoint.is_empty() && !token.is_empty() => {
            Ok(GatewayEnv {
                base_url: gateway_base_url(&endpoint),
                key: token,
            })
        }
        _ => bail!(
            "PROMPTFORGE_GATEWAY_URL and PROMPTFORGE_GATEWAY_API_KEY must both be set: \
             the papergate prompt binds its writer model through the gateway"
        ),
    }
}

/// The gateway base URL for the harness binding.
///
/// The harness derives the OpenAI-compatible API root itself by appending
/// `/v1` to the base URL it is bound with. The variable has been given as
/// that `/v1` root, so a trailing `/v1` is stripped here and either spelling
/// binds the same gateway.
fn gateway_base_url(endpoint: &str) -> String {
    let trimmed = endpoint.trim_end_matches('/');
    let base = trimmed.strip_suffix(GATEWAY_API_SUFFIX).unwrap_or(trimmed);
    base.trim_end_matches('/').to_owned()
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
    use std::num::NonZeroU32;
    use std::path::Path;

    use clap::Parser;
    use harness_api::{FailureKind, SessionEvent, SessionFailure};
    use paperstore::PaperNum;
    use paperstore_sqlite::SqliteBackend;
    use promptforge_api_runtime::types::models::{ModelDescriptor, ModelId, ThinkingMode};
    use promptforge_api_runtime::types::timestamp::Timestamp;
    use promptforge_api_runtime::{Environment, Prompt, Requirements, RunContext};
    use tempfile::TempDir;

    use super::{
        Cancelled, Cli, DEFAULT_MODEL, DEFAULT_PROMPT, PaperInput, Progress, catalog_binding,
        gateway_base_url, load_input_markdown, load_paper_md,
    };

    fn paper_num() -> PaperNum {
        PaperNum::parse("P4003R2").unwrap_or_else(|e| panic!("parse: {e}"))
    }

    /// One session event in the harness's persisted shape.
    fn event(index: u64, kind: &str, section: &str, text: Option<&str>) -> SessionEvent {
        let mut event = serde_json::json!({
            "kind": kind,
            "execution": "test",
            "section": section,
            "provenance": { "task": "0", "seq": index },
        });
        if let Some(text) = text {
            event["text"] = serde_json::Value::String(text.to_owned());
        }
        SessionEvent {
            index,
            reply: None,
            event,
        }
    }

    /// Prepares the embedded prompt the way the harness does at launch:
    /// every declared role filled from one descriptor, the requirements
    /// reported back.
    fn prepared_requirements(context: u32, thinking: ThinkingMode) -> Requirements {
        let (prompt, _parse_events) = Prompt::parse(DEFAULT_PROMPT, "test");
        let prompt = prompt.unwrap_or_else(|e| panic!("the embedded prompt must parse: {e}"));
        let descriptor = ModelDescriptor::new(
            ModelId::gateway(DEFAULT_MODEL).unwrap_or_else(|e| panic!("model id: {e}")),
            "a test model",
            NonZeroU32::new(context).unwrap_or_else(|| panic!("non-zero context")),
            thinking,
        );
        let context = RunContext::new("test", 0, Timestamp::UNIX_EPOCH).model(descriptor);
        let (_, requirements) = Environment::new().prepare(&prompt, context);
        requirements
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
        let cli = Cli::parse_from(["papergate", "p4003r2"]);
        assert_eq!(cli.paper.as_ref().map(PaperNum::as_str), Some("P4003R2"));
        assert_eq!(cli.file, None);
        assert_eq!(
            cli.output, None,
            "no --output means the report goes to stdout"
        );
        assert_eq!(cli.prompt, None);

        let cli = Cli::parse_from([
            "papergate",
            "P4003R2",
            "--output",
            "out/analysis.md",
            "--prompt",
            "custom.md",
        ]);
        assert_eq!(cli.output.as_deref(), Some(Path::new("out/analysis.md")));
        assert_eq!(cli.prompt.as_deref(), Some(Path::new("custom.md")));
    }

    #[test]
    fn parser_accepts_file_alone() {
        let cli = Cli::parse_from(["papergate", "--file", "paper.md"]);
        assert_eq!(cli.paper, None);
        assert_eq!(cli.file.as_deref(), Some(Path::new("paper.md")));
    }

    #[test]
    fn parser_defaults_the_model_and_accepts_an_override() {
        let cli = Cli::parse_from(["papergate", "--file", "paper.md"]);
        assert_eq!(cli.model, DEFAULT_MODEL);

        let cli = Cli::parse_from([
            "papergate",
            "--file",
            "paper.md",
            "--model",
            "analysis-large",
        ]);
        assert_eq!(cli.model, "analysis-large");
    }

    #[test]
    fn parser_rejects_both_inputs_and_neither() {
        assert!(
            Cli::try_parse_from(["papergate", "P4003R2", "--file", "paper.md"]).is_err(),
            "the input group must reject a number together with --file",
        );
        assert!(
            Cli::try_parse_from(["papergate"]).is_err(),
            "the input group must require exactly one input",
        );
    }

    #[test]
    fn parser_rejects_invalid_paper_numbers() {
        for args in [
            &["papergate", "4003"][..],
            &["papergate", "PR2"][..],
            &["papergate", ""][..],
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
            Cli::try_parse_from(["papergate", "P4003R2", "N4950"]).is_err(),
            "clap must reject a trailing argument instead of silently dropping it",
        );
        assert!(Cli::try_parse_from(["papergate", "--bogus", "P4003R2"]).is_err());
    }

    #[test]
    fn embedded_prompt_prepares_against_a_switchable_model() {
        let requirements = prepared_requirements(393_216, ThinkingMode::Switchable);
        assert!(
            requirements.is_satisfied(),
            "the writer role must be satisfied by a thinking-switchable model, which is \
             what the gateway serves; the harness refuses any unmet requirement: {requirements:?}",
        );
    }

    #[test]
    fn embedded_prompt_prepares_against_a_never_thinking_model() {
        let requirements = prepared_requirements(393_216, ThinkingMode::Never);
        assert!(
            requirements.is_satisfied(),
            "a never-thinking model satisfies the writer role outright: {requirements:?}",
        );
    }

    #[test]
    fn a_too_small_context_window_is_refused() {
        let requirements = prepared_requirements(8192, ThinkingMode::Switchable);
        assert!(
            !requirements.is_satisfied(),
            "an 8k model must fail the writer role's 32k minimum",
        );
        let notice = requirements.notice();
        assert!(
            notice.contains("writer") && notice.contains("32768"),
            "the refusal must name the role and its minimum: {notice}",
        );
    }

    #[test]
    fn catalog_binding_holds_the_one_model_by_id() {
        let catalog = catalog_binding("reasoning-large");
        assert_eq!(catalog.generation, 1);
        assert_eq!(
            catalog.models,
            vec![serde_json::json!({ "id": "reasoning-large" })],
            "the harness reads the entry's `id` as the fallback selection",
        );
    }

    #[test]
    fn gateway_base_url_strips_the_api_root_the_harness_appends() {
        for (given, expected) in [
            ("https://gw.example.com/v1", "https://gw.example.com"),
            ("https://gw.example.com/v1/", "https://gw.example.com"),
            ("https://gw.example.com", "https://gw.example.com"),
            ("https://gw.example.com/", "https://gw.example.com"),
            ("http://127.0.0.1:8081/v1", "http://127.0.0.1:8081"),
            ("https://gw.example.com/v1x", "https://gw.example.com/v1x"),
        ] {
            assert_eq!(gateway_base_url(given), expected, "given {given:?}");
        }
    }

    #[test]
    fn progress_reports_the_last_reply_of_a_succeeded_run() {
        let mut progress = Progress::default();
        assert_eq!(
            progress.absorb(&event(0, "run_started", "Papergate", None)),
            Some("[papergate] Papergate: run_started".to_owned()),
        );
        progress.absorb(&event(1, "assistant_reply", "Evaluate", Some("- evidence")));
        progress.absorb(&event(
            2,
            "assistant_reply",
            "Analyze",
            Some("Verdict: Strong\n"),
        ));
        progress.absorb(&event(3, "run_succeeded", "Papergate", None));

        let report = progress.report().unwrap_or_else(|e| panic!("report: {e}"));

        assert_eq!(report, "Verdict: Strong\n");
    }

    #[test]
    fn progress_skips_events_below_the_cursor_and_silent_kinds() {
        let mut progress = Progress::default();
        progress.absorb(&event(0, "run_started", "Papergate", None));
        progress.absorb(&event(1, "assistant_reply", "Analyze", Some("real")));
        assert_eq!(progress.cursor, 2);

        // A live copy of an event the transcript backfill already covered.
        assert_eq!(
            progress.absorb(&event(1, "assistant_reply", "Analyze", Some("stale"))),
            None
        );
        assert_eq!(progress.last_reply.as_deref(), Some("real"));

        // Raw model-turn bodies are absorbed (the cursor moves) but not echoed.
        assert_eq!(progress.absorb(&event(2, "request", "Analyze", None)), None);
        assert_eq!(
            progress.absorb(&event(3, "response", "Analyze", None)),
            None
        );
        assert_eq!(progress.cursor, 4);
    }

    #[test]
    fn progress_fails_when_the_run_never_reported_success() {
        let mut progress = Progress::default();
        progress.absorb(&event(
            0,
            "assistant_reply",
            "Analyze",
            Some("Verdict: Weak\n"),
        ));

        let error = match progress.report() {
            Ok(report) => panic!("a run without run_succeeded must fail, got {report:?}"),
            Err(error) => error.to_string(),
        };

        assert!(
            error.contains("without the run reporting success"),
            "the error must say the run never succeeded: {error}",
        );
    }

    #[test]
    fn progress_fails_with_the_session_failure_reports() {
        let mut progress = Progress::default();
        progress.absorb(&event(0, "run_started", "Papergate", None));
        progress.fail(SessionFailure {
            kind: FailureKind::RunFailed,
            message: "the environment cannot satisfy this prompt".to_owned(),
        });

        let error = match progress.report() {
            Ok(report) => panic!("a reported failure must fail the run, got {report:?}"),
            Err(error) => error.to_string(),
        };

        assert!(
            error.contains("run failed") && error.contains("cannot satisfy this prompt"),
            "the error must carry the harness's report: {error}",
        );
    }

    #[test]
    fn progress_fails_when_a_succeeded_run_has_no_reply() {
        let mut progress = Progress::default();
        progress.absorb(&event(0, "run_succeeded", "Papergate", None));

        let error = match progress.report() {
            Ok(report) => panic!("a run without a reply has no report, got {report:?}"),
            Err(error) => error.to_string(),
        };

        assert!(
            error.contains("without an assistant reply"),
            "the error must name the missing reply: {error}",
        );
    }

    #[test]
    fn a_cancelled_progress_reports_cancellation_over_everything_else() {
        let mut progress = Progress::default();
        progress.absorb(&event(0, "assistant_reply", "Analyze", Some("partial")));
        progress.fail(SessionFailure {
            kind: FailureKind::Interrupted,
            message: "interrupted".to_owned(),
        });
        progress.cancelled = true;

        let error = match progress.report() {
            Ok(report) => panic!("a cancelled run has no report, got {report:?}"),
            Err(error) => error,
        };

        assert!(
            error.downcast_ref::<Cancelled>().is_some(),
            "main selects exit 130 from the Cancelled marker: {error}",
        );
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
