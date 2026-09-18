//! Application orchestration for the `papergate` CLI.
//!
//! `main` owns the process boundary (argument parsing, signal installation,
//! exit status). This module owns everything between: it validates the gateway
//! environment, resolves the prompt source (the embedded vendored prompt by
//! default, `--prompt` from disk otherwise), loads the paper markdown (from
//! the SQLite paper store for a paper number, verbatim from disk for
//! `--file`), binds the prompt's declared model role to one gateway model,
//! seeds the run's store with the paper under the prompt's declared
//! `paper.md` input key, runs the prompt, and extracts the prompt's declared
//! `report.md` output to `--output`, or to stdout when no path is given.

use std::path::{Path, PathBuf};
use std::sync::Arc;

use anyhow::{Context, Result, bail};
use clap::Parser;
use paperstore::{PaperNum, StorageBackend};
use paperstore_sqlite::SqliteBackend;
use promptforge_api_runtime::client::{
    GatewayClient, GatewayEndpoint, SecretString, fetch_model_catalog,
};
use promptforge_api_runtime::types::cancel::CancelHandle;
use promptforge_api_runtime::types::models::{ModelCatalog, ModelDescriptor, ModelId};
use promptforge_api_runtime::types::observe::{Observation, Observer};
use promptforge_api_runtime::{
    Environment, Prompt, RequirementCheck, Requirements, RunContext, RunResult, execute,
};
use shared_vfs::{Origin, VfsError, VfsRef};

/// The embedded papergate prompt.
const DEFAULT_PROMPT: &str = include_str!("../papergate.md");

/// The gateway model the prompt's `writer` role binds to unless `--model`
/// or `PAPERGATE_MODEL` names another. The capability-named catalog entry
/// every C++ Alliance gateway serves.
const DEFAULT_MODEL: &str = "reasoning-large";

/// The mount prefix of the run-scoped store inside the run's virtual
/// filesystem. Mirrors promptforge's `STORE_MOUNT`, which lives in a crate
/// private to the promptforge family; the prompt's `store.read("paper.md")`
/// resolves to `<STORE_MOUNT>/paper.md`, so the host seeds and extracts
/// through the same prefix.
const STORE_MOUNT: &str = "/_promptforge/store";

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
/// The runtime reports cancellation as a value, not an error; this type
/// carries it through the `anyhow` chain so `main` can select exit code 130.
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
/// Returns an error if either gateway variable is unset or blank, the prompt
/// fails to parse, the paper input cannot be loaded (`WG21_DATA_DIR` unset,
/// the number missing from the store or without converted markdown, or the
/// `--file` path unreadable), the model catalog cannot be fetched or lacks
/// the requested model, the prompt's declared requirements are unmet by that
/// model, execution fails, the run is cancelled ([`Cancelled`]), or the
/// prompt did not produce its declared `report.md` output.
pub(crate) async fn run(request: RunRequest<'_>) -> Result<()> {
    let RunRequest {
        input,
        output,
        prompt,
        model,
        cancel,
    } = request;
    let (endpoint, token) = gateway_from_env()?;
    let execution = format!(
        "papergate-{:016x}{:016x}",
        fastrand::u64(..),
        fastrand::u64(..)
    );

    let source = match prompt {
        Some(path) => tokio::fs::read_to_string(path)
            .await
            .with_context(|| format!("read prompt file {}", path.display()))?,
        None => DEFAULT_PROMPT.to_owned(),
    };
    let observer: Arc<dyn Observer> = Arc::new(StderrObserver);
    let parsed = Prompt::parse(&source, &execution, observer.as_ref())
        .context("parse the papergate prompt")?;

    // Load before the catalog fetch: a store miss or an unreadable file
    // fails fast, before any network call.
    let paper_md = load_input_markdown(input).await?;

    let catalog = fetch_model_catalog(&endpoint, &token)
        .await
        .context("fetch the model catalog")?;
    let descriptor = select_model(&catalog, model)?;
    let client = GatewayClient::new(
        GatewayEndpoint::new(&endpoint).context("parse PROMPTFORGE_GATEWAY_URL")?,
        SecretString::new(token).context("read PROMPTFORGE_GATEWAY_API_KEY")?,
    );

    // Prepare by hand rather than through `Environment::run`: the prepared
    // context owns the run's fresh store, and the paper must be seeded into
    // it before the run starts and the report read out of it after.
    let context = RunContext::new(execution.as_str())
        .observer(observer)
        .cancel(cancel)
        .client(client)
        .model(descriptor);
    let (context, requirements) = Environment::new().prepare(&parsed, context);
    check_requirements(&requirements, model)?;
    let vfs = context.vfs_handle().clone();
    seed_store(&vfs, &paper_md)?;

    match execute::run(&parsed, "", context).await {
        RunResult::Ok(_) => {}
        RunResult::Cancelled => return Err(Cancelled.into()),
        RunResult::Failure(error) => {
            return Err(anyhow::Error::from(error).context("run the papergate prompt"));
        }
    }

    let report = read_report(&vfs)?;
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

/// Reads the gateway environment, requiring both variables.
///
/// The prompt binds its `writer` role through the gateway, so there is no
/// local-only mode: a missing credential is a startup error naming both
/// variables rather than a silent downgrade.
fn gateway_from_env() -> Result<(String, String)> {
    let endpoint = env_optional("PROMPTFORGE_GATEWAY_URL")?;
    let token = env_optional("PROMPTFORGE_GATEWAY_API_KEY")?;
    let endpoint = endpoint.map(|value| value.trim().to_owned());
    let token = token.map(|value| value.trim().to_owned());
    match (endpoint, token) {
        (Some(endpoint), Some(token)) if !endpoint.is_empty() && !token.is_empty() => {
            Ok((endpoint, token))
        }
        _ => bail!(
            "PROMPTFORGE_GATEWAY_URL and PROMPTFORGE_GATEWAY_API_KEY must both be set: \
             the papergate prompt binds its writer model through the gateway"
        ),
    }
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

/// Picks the descriptor named `model` out of the gateway's catalog.
///
/// The runtime binds every role the prompt declares to this one model and
/// checks the role's hard requirements against it at prepare. A name the
/// gateway does not serve is an error listing what it does serve, so a
/// misconfigured `PAPERGATE_MODEL` is diagnosable from the message alone.
fn select_model(catalog: &ModelCatalog, model: &str) -> Result<ModelDescriptor> {
    let id = ModelId::gateway(model).with_context(|| format!("parse model name {model:?}"))?;
    if let Some(descriptor) = catalog.get(&id) {
        return Ok(descriptor.clone());
    }
    let available: Vec<&str> = catalog
        .models()
        .iter()
        .map(|descriptor| descriptor.id().name())
        .collect();
    bail!("the gateway does not serve model {model:?}; it serves {available:?}")
}

/// Refuses to run a prompt whose prepare-time requirements are unmet, with
/// one deliberate tolerance.
///
/// The prompt's `writer` role declares the `no-thinking` hard keyword, which
/// is also how the runtime learns to send `enable_thinking: false` on every
/// request. The runtime's fill check accepts that keyword only for a model
/// that can never think, so a `Switchable` model (the only kind the C++
/// Alliance gateway serves) is reported as unmet even though the request
/// switch does exactly what the role asks. That one report is tolerated
/// here and the run proceeds with thinking off; every other unmet
/// requirement, missing capability, or conflict is an error.
fn check_requirements(requirements: &Requirements, model: &str) -> Result<()> {
    if requirements.is_satisfied() {
        return Ok(());
    }
    let tolerated = |unmet: &promptforge_api_runtime::UnmetRequirement| {
        unmet.check == RequirementCheck::HardKeyword
            && unmet.required == "no-thinking"
            && unmet.actual == "Switchable"
    };
    let blocking = requirements
        .unmet_requirements
        .iter()
        .any(|unmet| !tolerated(unmet))
        || !requirements.missing_required.is_empty()
        || !requirements.conflicts.is_empty();
    if blocking {
        bail!("the prompt's declared requirements are unmet by model {model}: {requirements:?}");
    }
    eprintln!(
        "note: model {model} is thinking-switchable; running with thinking off as the \
         prompt's no-thinking role requests"
    );
    Ok(())
}

/// The full store path of a prompt-relative store file.
fn store_path(name: &str) -> String {
    format!("{STORE_MOUNT}/{name}")
}

/// Seeds the run's store with the paper under the prompt's declared input key.
///
/// The access is dropped on return, so its claim never meets the run's own
/// identities.
fn seed_store(vfs: &VfsRef, paper_md: &str) -> Result<()> {
    let access = vfs
        .acquire(Origin::new("papergate seed"))
        .context("open the run store for seeding")?;
    access
        .write(&store_path("paper.md"), paper_md.as_bytes())
        .context("seed the run store with paper.md")
}

/// Reads the prompt's declared output from the run's store.
///
/// A missing `report.md` is an explicit error naming the prompt's output
/// contract, never an empty write.
fn read_report(vfs: &VfsRef) -> Result<String> {
    let access = vfs
        .acquire(Origin::new("papergate report"))
        .context("open the run store for the report")?;
    match access.read_string(&store_path("report.md")) {
        Ok(report) => Ok(report),
        Err(error @ VfsError::NotFound(_)) => Err(error).context(
            "the prompt did not produce its declared output: report.md is missing \
             from the run store",
        ),
        Err(error) => Err(error).context("read report.md from the run store"),
    }
}

/// An observer that writes one progress line per event to stderr.
#[derive(Debug)]
struct StderrObserver;

impl Observer for StderrObserver {
    fn observe(&self, execution: &str, section: &str, event: Observation) {
        use std::io::Write as _;
        // Observers must not panic and progress is a side channel, so a failed
        // write to stderr is deliberately dropped rather than surfaced.
        let _ignored = writeln!(std::io::stderr(), "[{execution}] {section}: {event}");
    }
}

#[cfg(test)]
mod tests {
    use std::num::NonZeroU32;
    use std::path::Path;

    use clap::Parser;
    use paperstore::PaperNum;
    use paperstore_sqlite::SqliteBackend;
    use promptforge_api_runtime::types::models::{
        ModelCatalog, ModelDescriptor, ModelId, ThinkingMode,
    };
    use promptforge_api_runtime::types::observe::NullObserver;
    use promptforge_api_runtime::{Environment, Prompt, RunContext};
    use shared_vfs::{MemoryBackend, Origin, VfsRef};
    use tempfile::TempDir;

    use super::{
        Cli, DEFAULT_MODEL, DEFAULT_PROMPT, PaperInput, STORE_MOUNT, check_requirements,
        load_input_markdown, load_paper_md, read_report, seed_store, select_model, store_path,
    };

    /// A run store shaped like the runtime's: a fresh memory backend at the
    /// store mount.
    fn run_store() -> VfsRef {
        VfsRef::builder()
            .mount(STORE_MOUNT, MemoryBackend::new())
            .build()
    }

    fn read_store(vfs: &VfsRef, name: &str) -> String {
        let access = vfs
            .acquire(Origin::new("test read"))
            .unwrap_or_else(|e| panic!("acquire: {e}"));
        access
            .read_string(&store_path(name))
            .unwrap_or_else(|e| panic!("read {name}: {e}"))
    }

    fn write_store(vfs: &VfsRef, name: &str, contents: &str) {
        let access = vfs
            .acquire(Origin::new("test write"))
            .unwrap_or_else(|e| panic!("acquire: {e}"));
        access
            .write(&store_path(name), contents.as_bytes())
            .unwrap_or_else(|e| panic!("write {name}: {e}"));
    }

    fn descriptor(name: &str, context: u32, thinking: ThinkingMode) -> ModelDescriptor {
        ModelDescriptor::new(
            ModelId::gateway(name).unwrap_or_else(|e| panic!("model id: {e}")),
            "a test model",
            NonZeroU32::new(context).unwrap_or_else(|| panic!("non-zero context")),
            thinking,
        )
    }

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
    fn embedded_prompt_prepares_against_a_switchable_default_model() {
        let prompt = Prompt::parse(DEFAULT_PROMPT, "test", &NullObserver::default())
            .unwrap_or_else(|e| panic!("the embedded prompt must parse: {e}"));
        let context = RunContext::new("test").model(descriptor(
            DEFAULT_MODEL,
            393_216,
            ThinkingMode::Switchable,
        ));

        let (context, requirements) = Environment::new().prepare(&prompt, context);

        check_requirements(&requirements, DEFAULT_MODEL).unwrap_or_else(|e| {
            panic!("a switchable model must be accepted for the no-thinking writer role: {e}")
        });
        assert!(
            context.vfs_handle().acquire(Origin::new("probe")).is_ok(),
            "prepare must hand back a usable run store",
        );
    }

    #[test]
    fn embedded_prompt_prepares_cleanly_against_a_never_thinking_model() {
        let prompt = Prompt::parse(DEFAULT_PROMPT, "test", &NullObserver::default())
            .unwrap_or_else(|e| panic!("the embedded prompt must parse: {e}"));
        let context =
            RunContext::new("test").model(descriptor("plain", 393_216, ThinkingMode::Never));

        let (_, requirements) = Environment::new().prepare(&prompt, context);

        assert!(
            requirements.is_satisfied(),
            "a never-thinking model satisfies the writer role outright: {requirements:?}",
        );
    }

    #[test]
    fn a_too_small_context_window_is_refused() {
        let prompt = Prompt::parse(DEFAULT_PROMPT, "test", &NullObserver::default())
            .unwrap_or_else(|e| panic!("the embedded prompt must parse: {e}"));
        let context =
            RunContext::new("test").model(descriptor("tiny", 8192, ThinkingMode::Switchable));

        let (_, requirements) = Environment::new().prepare(&prompt, context);

        let error = match check_requirements(&requirements, "tiny") {
            Ok(()) => panic!("an 8k model must fail the writer role's 32k minimum"),
            Err(error) => error.to_string(),
        };
        assert!(
            error.contains("tiny") && error.contains("ContextMinimum"),
            "the error must name the model and the failed check: {error}",
        );
    }

    #[test]
    fn select_model_returns_the_named_descriptor() {
        let wanted = descriptor("reasoning-large", 393_216, ThinkingMode::Switchable);
        let catalog = ModelCatalog::new(vec![
            descriptor("other", 8192, ThinkingMode::Never),
            wanted.clone(),
        ])
        .unwrap_or_else(|e| panic!("catalog: {e}"));

        let selected =
            select_model(&catalog, "reasoning-large").unwrap_or_else(|e| panic!("select: {e}"));

        assert_eq!(selected, wanted);
    }

    #[test]
    fn select_model_names_the_available_models_when_missing() {
        let catalog = ModelCatalog::new(vec![descriptor("other", 8192, ThinkingMode::Never)])
            .unwrap_or_else(|e| panic!("catalog: {e}"));

        let error = match select_model(&catalog, "reasoning-large") {
            Ok(descriptor) => panic!("an unknown model must fail, got {descriptor:?}"),
            Err(error) => error.to_string(),
        };

        assert!(
            error.contains("reasoning-large") && error.contains("other"),
            "the error must name the requested and the served models: {error}",
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

    #[test]
    fn seeding_writes_the_input_verbatim_under_paper_md() {
        let vfs = run_store();
        let contents = "# Paper\n\nunicode \u{201c}quotes\u{201d} and trailing space \n\n";

        seed_store(&vfs, contents).unwrap_or_else(|e| panic!("seed store: {e}"));

        assert_eq!(read_store(&vfs, "paper.md"), contents);
    }

    #[test]
    fn read_report_returns_the_store_report_verbatim() {
        let vfs = run_store();
        write_store(&vfs, "report.md", "Verdict: Strong\n");

        let report = read_report(&vfs).unwrap_or_else(|e| panic!("read report: {e}"));

        assert_eq!(report, "Verdict: Strong\n");
    }

    #[test]
    fn missing_report_is_an_explicit_contract_error() {
        let vfs = run_store();

        let error = match read_report(&vfs) {
            Ok(report) => panic!("a missing report.md must fail, got {report:?}"),
            Err(error) => error.to_string(),
        };

        assert!(
            error.contains("declared output") && error.contains("report.md"),
            "the error must name the prompt's output contract: {error}",
        );
    }
}
