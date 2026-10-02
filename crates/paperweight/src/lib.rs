//! Run a promptforge prompt against one WG21 paper from the command line.
//!
//! `<bin> [PAPER_NUM] [--file <PATH>] [--output <PATH>] [--prompt <PATH>]
//! [--model <ID>] [--args <TEXT>]` runs a promptforge prompt against one WG21
//! paper as a harness session and writes the prompt's declared output to
//! stdout, or to `--output` when given. The prompt is the embedded papergate
//! prompt unless `--prompt` names a file; the run takes its name from the
//! prompt's file stem (`papergate` for the embedded one). Exactly one input is
//! required: a paper number resolved through the SQLite paper store, or
//! `--file` to read a markdown file verbatim. A paper number needs
//! `WG21_DATA_DIR` pointing at the paperflow workspace; `--file` never touches
//! it. The gateway credentials `PROMPTFORGE_GATEWAY_URL` (the gateway origin; a
//! trailing `/v1` is dropped) and `PROMPTFORGE_GATEWAY_API_KEY` must both be
//! set: the prompt binds its models through the gateway, so a local-only run
//! can only fail. `--model` selects the gateway model; without it, the run
//! binds the first chat model the gateway lists.
//!
//! The crate builds two binaries, `papergate` and `promptforge-cli`, both thin
//! wrappers over [`run_cli`].

use std::error::Error;
use std::process::ExitCode;

use clap::{CommandFactory as _, FromArgMatches as _};
use harness::cancel::CancelHandle;

use crate::app::{Cancelled, Cli, RunRequest};

mod app;

/// Parses arguments under the program name `name`, runs the prompt, and maps
/// its result to a process exit status.
///
/// `clap` owns usage failures and their status; this returns 130 for a
/// cancelled run and 1 for any other failure.
///
/// # Panics
/// Panics if the Tokio runtime cannot be built.
#[must_use]
#[tokio::main(flavor = "current_thread")]
pub async fn run_cli(name: &'static str) -> ExitCode {
    let matches = Cli::command().name(name).bin_name(name).get_matches();
    let cli = match Cli::from_arg_matches(&matches) {
        Ok(cli) => cli,
        Err(error) => error.exit(),
    };
    let cancel = install_cancel();
    let input = cli.input();
    let request = RunRequest {
        input: &input,
        output: cli.output.as_deref(),
        prompt: cli.prompt.as_deref(),
        model: cli.model.as_deref(),
        args: &cli.args,
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

/// Maps a run failure to a process exit code: 130 for a Ctrl-C close (the
/// conventional interrupted code), 1 for every other failure.
fn exit_code(error: &anyhow::Error) -> u8 {
    let cancelled = error.chain().any(<dyn Error>::is::<Cancelled>);
    if cancelled { 130 } else { 1 }
}
