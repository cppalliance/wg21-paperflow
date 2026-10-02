//! The `promptforge-cli` command: see the `papergate` library crate.

use std::process::ExitCode;

fn main() -> ExitCode {
    papergate::run_cli(env!("CARGO_BIN_NAME"))
}
