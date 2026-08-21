//! Application orchestration for the `papergate` CLI.
//!
//! `main` owns the process boundary (argument parsing, signal installation,
//! exit status). This module owns everything between: it validates the gateway
//! environment, resolves the prompt source (the embedded vendored prompt by
//! default, `--prompt` from disk otherwise), seeds a fresh per-run store with
//! the paper under the prompt's declared `paper.md` input key, runs the prompt
//! against the live model catalog, and extracts the prompt's declared
//! `report.md` output to the requested path.

use std::path::{Path, PathBuf};
use std::sync::Arc;

use anyhow::{Context, Result, bail};
use clap::Parser;
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
    about = "Report on the evidence a WG21 paper provides for its need of standardization"
)]
pub(crate) struct Cli {
    /// Path to the WG21 paper markdown file to analyze.
    pub(crate) paper: PathBuf,
    /// Where to write the analysis report.
    #[arg(long, value_name = "PATH", default_value = "report.md")]
    pub(crate) output: PathBuf,
    /// Read the prompt from PATH instead of the embedded papergate prompt.
    #[arg(long, value_name = "PATH")]
    pub(crate) prompt: Option<PathBuf>,
}

/// A single analysis run: what to read, where to write, and cancellation.
pub(crate) struct RunRequest<'a> {
    /// The paper markdown file to analyze.
    pub(crate) paper: &'a Path,
    /// Where the analysis report is written.
    pub(crate) output: &'a Path,
    /// An optional prompt file overriding the embedded default.
    pub(crate) prompt: Option<&'a Path>,
    /// The cooperative cancellation handle wired to Ctrl-C.
    pub(crate) cancel: CancelHandle,
}

impl std::fmt::Debug for RunRequest<'_> {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("RunRequest")
            .field("paper", &self.paper)
            .field("output", &self.output)
            .field("prompt", &self.prompt)
            .finish_non_exhaustive()
    }
}

/// Runs one analysis using the gateway configuration read from the environment.
///
/// # Errors
/// Returns an error if either gateway variable is unset or blank, the paper or
/// prompt file cannot be read, the prompt fails to parse, the model catalog
/// cannot be fetched, execution fails (including cooperative cancellation), or
/// the prompt did not produce its declared `report.md` output.
pub(crate) async fn run(request: RunRequest<'_>) -> Result<()> {
    let RunRequest {
        paper,
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

    let models = fetch_model_catalog(&endpoint, &token)
        .await
        .context("fetch the model catalog")?;
    // The prompt defines its own tools via `tools.add_local`, so the picker
    // indexes an empty catalog and the run receives an empty tool slice.
    let picker = ToolPicker::build(Catalog::new(Vec::new()), PickerConfig::default())
        .context("build the tool picker")?;

    let paper_md = tokio::fs::read_to_string(paper)
        .await
        .with_context(|| format!("read paper file {}", paper.display()))?;

    let output = output.to_owned();
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
        extract_report(&store, &output)
    })
    .await?;

    println!("{}", written.display());
    Ok(())
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

/// Extracts the prompt's declared output from the store and writes it to disk.
///
/// A missing `report.md` is an explicit error naming the prompt's output
/// contract, never an empty-file write.
fn extract_report(store: &StoreRef, output: &Path) -> Result<()> {
    let report = match store.read("report.md") {
        Ok(report) => report,
        Err(error @ StoreError::NotFound { .. }) => {
            return Err(error).context(
                "the prompt did not produce its declared output: report.md is missing \
                 from the run store",
            );
        }
        Err(error) => return Err(error).context("read report.md from the run store"),
    };
    std::fs::write(output, report)
        .with_context(|| format!("write the report to {}", output.display()))
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
    use promptforge_core::store::{FileStore, StoreRef};
    use tempfile::TempDir;

    use super::{Cli, extract_report, seed_store, with_temp_store};

    fn file_store(dir: &TempDir) -> StoreRef {
        let backend =
            FileStore::new(dir.path()).unwrap_or_else(|e| panic!("create file store: {e}"));
        StoreRef::new(Box::new(backend))
    }

    #[test]
    fn parser_accepts_paper_with_flag_defaults() {
        let cli = Cli::parse_from(["papergate", "paper.md"]);
        assert_eq!(cli.paper, Path::new("paper.md"));
        assert_eq!(cli.output, Path::new("report.md"));
        assert_eq!(cli.prompt, None);

        let cli = Cli::parse_from([
            "papergate",
            "paper.md",
            "--output",
            "out/analysis.md",
            "--prompt",
            "custom.md",
        ]);
        assert_eq!(cli.output, Path::new("out/analysis.md"));
        assert_eq!(cli.prompt.as_deref(), Some(Path::new("custom.md")));
    }

    #[test]
    fn parser_rejects_missing_positional_unknown_flag_and_extras() {
        assert!(Cli::try_parse_from(["papergate"]).is_err());
        assert!(
            Cli::try_parse_from(["papergate", "a.md", "b.md"]).is_err(),
            "clap must reject a trailing argument instead of silently dropping it",
        );
        assert!(Cli::try_parse_from(["papergate", "--bogus", "a.md"]).is_err());
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
    fn extraction_writes_the_output_file_from_the_store_report() {
        let dir = TempDir::new().unwrap_or_else(|e| panic!("create temp dir: {e}"));
        let store = file_store(&dir);
        store
            .write("report.md", "Verdict: Strong\n")
            .unwrap_or_else(|e| panic!("write report.md: {e}"));
        let output = dir.path().join("analysis.md");

        extract_report(&store, &output).unwrap_or_else(|e| panic!("extract report: {e}"));

        let written =
            std::fs::read_to_string(&output).unwrap_or_else(|e| panic!("read output file: {e}"));
        assert_eq!(written, "Verdict: Strong\n");
    }

    #[test]
    fn missing_report_is_an_explicit_contract_error_and_writes_nothing() {
        let dir = TempDir::new().unwrap_or_else(|e| panic!("create temp dir: {e}"));
        let store = file_store(&dir);
        let output = dir.path().join("analysis.md");

        let error = match extract_report(&store, &output) {
            Ok(()) => panic!("a missing report.md must fail"),
            Err(error) => error.to_string(),
        };

        assert!(
            error.contains("declared output") && error.contains("report.md"),
            "the error must name the prompt's output contract: {error}",
        );
        assert!(
            !output.exists(),
            "a missing report must never become an empty-file write",
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
