//! Application orchestration for the `papergate` CLI.
//!
//! `main` owns the process boundary (argument parsing, signal installation,
//! exit status). This module owns everything between: it validates the gateway
//! environment, resolves the prompt source (the embedded vendored prompt by
//! default, `--prompt` from disk otherwise), loads the paper markdown (from
//! the SQLite paper store for a paper number, verbatim from disk for
//! `--file`), seeds a fresh per-run store with the paper under the prompt's
//! declared `paper.md` input key, runs the prompt against the live model
//! catalog, and extracts the prompt's declared `report.md` output to
//! `--output`, or to stdout when no path is given.

use std::path::{Path, PathBuf};
use std::sync::Arc;

use anyhow::{Context, Result, bail};
use clap::Parser;
use paperstore::{PaperNum, StorageBackend};
use paperstore_sqlite::SqliteBackend;
use promptforge_core::CancelHandle;
use promptforge_core::execute::{self, ResolutionContext, RunConfig};
use promptforge_core::model::fetch_model_catalog;
use promptforge_core::observe::{Observation, Observer};
use promptforge_core::parser::Prompt;
use promptforge_core::store::{FileStore, StoreError, StoreRef};
use promptforge_tool_picker::{Catalog, Config as PickerConfig, ToolPicker};

/// The embedded papergate prompt, vendored from the promptforge prompts.
const DEFAULT_PROMPT: &str = include_str!("../papergate.md");

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
            .finish_non_exhaustive()
    }
}

/// Runs one analysis using the gateway configuration read from the environment.
///
/// # Errors
/// Returns an error if either gateway variable is unset or blank, the prompt
/// fails to parse, the paper input cannot be loaded (`WG21_DATA_DIR` unset,
/// the number missing from the store or without converted markdown, or the
/// `--file` path unreadable), the model catalog cannot be fetched, execution
/// fails (including cooperative cancellation), or the prompt did not produce
/// its declared `report.md` output.
pub(crate) async fn run(request: RunRequest<'_>) -> Result<()> {
    let RunRequest {
        input,
        output,
        prompt,
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

    let models = fetch_model_catalog(&endpoint, &token)
        .await
        .context("fetch the model catalog")?;
    // The prompt defines its own tools via `tools.add_local`, so the picker
    // indexes an empty catalog and the run receives an empty tool slice.
    let picker = ToolPicker::build(Catalog::new(Vec::new()), PickerConfig::default())
        .context("build the tool picker")?;

    let output = output.map(Path::to_owned);
    let written = output.clone();
    let execution_id = execution.clone();
    with_temp_store(&execution, move |store| async move {
        seed_store(&store, &paper_md)?;
        let config = RunConfig::new(execution_id.as_str())
            .observer(observer)
            .cancel(cancel);
        execute::run(
            &parsed,
            "",
            ResolutionContext::new(&picker, &models),
            &[],
            &store,
            config,
        )
        .await?;
        let report = read_report(&store)?;
        match &output {
            Some(path) => std::fs::write(path, &report)
                .with_context(|| format!("write the report to {}", path.display()))?,
            None => write_stdout(report.as_bytes())?,
        }
        Ok(())
    })
    .await?;

    if let Some(path) = &written {
        println!("{}", path.display());
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
/// The prompt binds its writer model with `models.default("writer", ...)`, so
/// there is no local-only mode: a missing credential is a startup error naming
/// both variables rather than a silent downgrade.
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

/// Runs `f` with a fresh per-run file store under the system temp dir, then
/// removes the store directory whether the run succeeded or failed.
///
/// The store is per-run scratch: the prompt appends `evidence.md` across its
/// fanout sections, so a reused directory would leak evidence between runs.
async fn with_temp_store<F, Fut>(execution: &str, f: F) -> Result<()>
where
    F: FnOnce(StoreRef) -> Fut,
    Fut: std::future::Future<Output = Result<()>>,
{
    let dir = std::env::temp_dir().join(execution);
    let backend = FileStore::new(&dir)
        .with_context(|| format!("create store directory {}", dir.display()))?;
    let store = StoreRef::new(Box::new(backend));
    let result = f(store).await;
    // Best-effort: a cleanup failure must not mask the run's own outcome.
    let _ignored = std::fs::remove_dir_all(&dir);
    result
}

/// Seeds the run store with the paper under the prompt's declared input key.
fn seed_store(store: &StoreRef, paper_md: &str) -> Result<()> {
    store
        .write("paper.md", paper_md)
        .context("seed the run store with paper.md")
}

/// Reads the prompt's declared output from the run store.
///
/// A missing `report.md` is an explicit error naming the prompt's output
/// contract, never an empty write.
fn read_report(store: &StoreRef) -> Result<String> {
    match store.read("report.md") {
        Ok(report) => Ok(report),
        Err(error @ StoreError::NotFound { .. }) => Err(error).context(
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
    use std::path::Path;

    use clap::Parser;
    use paperstore::PaperNum;
    use paperstore_sqlite::SqliteBackend;
    use promptforge_core::store::{FileStore, StoreRef};
    use tempfile::TempDir;

    use super::{
        Cli, PaperInput, load_input_markdown, load_paper_md, read_report, seed_store,
        with_temp_store,
    };

    fn file_store(dir: &TempDir) -> StoreRef {
        let backend =
            FileStore::new(dir.path()).unwrap_or_else(|e| panic!("create file store: {e}"));
        StoreRef::new(Box::new(backend))
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
        assert_eq!(cli.output, None, "no --output means the report goes to stdout");
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
        let dir = TempDir::new().unwrap_or_else(|e| panic!("create temp dir: {e}"));
        let store = file_store(&dir);
        let contents = "# Paper\n\nunicode \u{201c}quotes\u{201d} and trailing space \n\n";

        seed_store(&store, contents).unwrap_or_else(|e| panic!("seed store: {e}"));

        let readback = store
            .read("paper.md")
            .unwrap_or_else(|e| panic!("read paper.md: {e}"));
        assert_eq!(readback, contents);
    }

    #[test]
    fn read_report_returns_the_store_report_verbatim() {
        let dir = TempDir::new().unwrap_or_else(|e| panic!("create temp dir: {e}"));
        let store = file_store(&dir);
        store
            .write("report.md", "Verdict: Strong\n")
            .unwrap_or_else(|e| panic!("write report.md: {e}"));

        let report = read_report(&store).unwrap_or_else(|e| panic!("read report: {e}"));

        assert_eq!(report, "Verdict: Strong\n");
    }

    #[test]
    fn missing_report_is_an_explicit_contract_error() {
        let dir = TempDir::new().unwrap_or_else(|e| panic!("create temp dir: {e}"));
        let store = file_store(&dir);

        let error = match read_report(&store) {
            Ok(report) => panic!("a missing report.md must fail, got {report:?}"),
            Err(error) => error.to_string(),
        };

        assert!(
            error.contains("declared output") && error.contains("report.md"),
            "the error must name the prompt's output contract: {error}",
        );
    }

    #[tokio::test]
    async fn temp_store_dir_is_removed_after_a_successful_run() {
        let execution = format!("papergate-test-{:016x}", fastrand::u64(..));
        let dir = std::env::temp_dir().join(&execution);
        let probe = dir.clone();

        let result = with_temp_store(&execution, move |store| async move {
            assert!(probe.is_dir(), "the store dir must exist during the run");
            seed_store(&store, "# Paper\n")?;
            Ok(())
        })
        .await;

        result.unwrap_or_else(|e| panic!("run: {e}"));
        assert!(
            !dir.exists(),
            "the store dir must be removed after a successful run",
        );
    }

    #[tokio::test]
    async fn temp_store_dir_is_removed_after_a_failed_run() {
        let execution = format!("papergate-test-{:016x}", fastrand::u64(..));
        let dir = std::env::temp_dir().join(&execution);

        let result =
            with_temp_store(&execution, |_store| async { Err(anyhow::anyhow!("boom")) }).await;

        assert!(result.is_err(), "the run's failure must propagate");
        assert!(
            !dir.exists(),
            "the store dir must be removed after a failed run",
        );
    }
}
