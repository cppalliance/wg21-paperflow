//! The `papergate` command-line tool.
//!
//! `papergate [PAPER_NUM] [--file <PATH>] [--output <PATH>] [--prompt <PATH>]
//! [--model <NAME>]` runs the embedded papergate promptforge prompt against
//! one WG21 paper and writes the analysis report to stdout, or to `--output`
//! when given. Exactly one input is required: a paper number resolved through
//! the SQLite paper store, or `--file` to read a markdown file verbatim. A
//! paper number needs `WG21_DATA_DIR` pointing at the paperflow workspace;
//! `--file` never touches it. The gateway credentials
//! `PROMPTFORGE_GATEWAY_URL` and `PROMPTFORGE_GATEWAY_API_KEY` must both be
//! set: the prompt binds its writer model through the gateway, so a
//! local-only run can only fail. `--model` (or `PAPERGATE_MODEL`) names the
//! gateway model that role binds to.
//!
//! The prompt runs as an agent session in the promptforge harness
//! (`harness-api`), the engine's production host. `main` is the process
//! boundary: it parses arguments, installs the Ctrl-C signal, invokes the
//! application runner, and selects the exit status. All orchestration lives
//! in [`app`].

use std::process::ExitCode;

use clap::Parser;
use harness_api::cancel::CancelHandle;

use crate::app::{Cancelled, Cli, RunRequest};

mod app;

/// Parses arguments, runs the analysis, and maps its result to a process exit
/// status. `clap` owns usage failures and their status; this returns 130 for a
/// cancelled run and 1 for any other failure.
///
/// The harness performs the run's effects on tokio tasks and its store
/// operations on the blocking pool, so the default multi-threaded runtime is
/// the right host for it.
#[tokio::main]
async fn main() -> ExitCode {
    let cli = Cli::parse();
    let cancel = install_cancel();
    let input = cli.input();
    let request = RunRequest {
        input: &input,
        output: cli.output.as_deref(),
        prompt: cli.prompt.as_deref(),
        model: &cli.model,
        cancel,
    };
    match app::run(request).await {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("error: {error:?}");
            ExitCode::from(exit_code(&error))
        }
    }
}

/// Installs a Ctrl-C handler that trips the returned cancellation handle once.
///
/// A failure to register the signal listener is reported to stderr rather than
/// discarded: the run simply stays non-cancellable in that case.
fn install_cancel() -> CancelHandle {
    let cancel = CancelHandle::new();
    let signal_cancel = cancel.clone();
    tokio::spawn(async move {
        match tokio::signal::ctrl_c().await {
            Ok(()) => signal_cancel.cancel(),
            Err(error) => {
                eprintln!("warning: cannot listen for Ctrl-C, run is not cancellable: {error}");
            }
        }
    });
    cancel
}

/// Maps a run failure to a process exit code: 130 for a cooperative
/// cancellation (the conventional interrupted code), 1 for every other
/// failure. Cancellation arrives as the app's own [`Cancelled`] marker: the
/// session was closed on papergate's request before it produced a report.
fn exit_code(error: &anyhow::Error) -> u8 {
    let cancelled = error
        .chain()
        .any(|cause| cause.downcast_ref::<Cancelled>().is_some());
    if cancelled { 130 } else { 1 }
}
