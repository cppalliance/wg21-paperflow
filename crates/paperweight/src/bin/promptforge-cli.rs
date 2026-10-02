//! The `promptforge-cli` command: see the `paperweight` library crate.

use std::process::ExitCode;

fn main() -> ExitCode {
    paperweight::run_cli(env!("CARGO_BIN_NAME"))
}
