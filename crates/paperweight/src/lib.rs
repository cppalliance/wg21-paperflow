//! Run a runvil prompt against one WG21 paper from the command line.
//!
//! `<bin> <PAPER_NUM> [--output <PATH>] [--prompt <PATH>] [--model <ID>]
//! [--verbose]` runs a runvil prompt against one WG21 paper as a harness
//! session and writes the prompt's declared output to stdout, or to
//! `--output` when given. The prompt is the embedded paperweight prompt unless
//! `--prompt` names a file; the run takes its name from the prompt's file stem
//! (`paperweight` for the embedded one). The paper number is resolved through
//! the SQLite paper store, which needs `WG21_DATA_DIR` pointing at the
//! paperflow workspace. The gateway credentials `PROMPTFORGE_GATEWAY_URL` (the gateway origin; a
//! trailing `/v1` is dropped) and `PROMPTFORGE_GATEWAY_API_KEY` must both be
//! set: the prompt binds its models through the gateway, so a local-only run
//! can only fail. `--model` selects the gateway model; without it, the run
//! binds the first chat model the gateway lists. Progress goes to stderr;
//! `--verbose` adds every tool call, its full result, Lua log messages, and
//! model replies.
//!
//! The crate's `paperweight` binary is a thin wrapper over [`run_cli`].

use std::error::Error;
use std::process::ExitCode;

use clap::{CommandFactory as _, FromArgMatches as _};

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
    let request = RunRequest {
        paper: &cli.paper,
        output: cli.output.as_deref(),
        prompt: cli.prompt.as_deref(),
        model: cli.model.as_deref(),
        verbose: cli.verbose,
    };
    match app::run(request).await {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("error: {error:?}");
            ExitCode::from(exit_code(&error))
        }
    }
}

/// Maps a run failure to a process exit code: 130 for a Ctrl-C close (the
/// conventional interrupted code), 1 for every other failure.
fn exit_code(error: &anyhow::Error) -> u8 {
    let cancelled = error.chain().any(<dyn Error>::is::<Cancelled>);
    if cancelled { 130 } else { 1 }
}
