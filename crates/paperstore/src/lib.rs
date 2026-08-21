//! Abstract storage API for WG21 paperflow artifacts.
//!
//! Port of the abstract slice of the Python `paperstore` package: the error
//! type, paper number, metadata row, the [`StorageBackend`] trait, and
//! workspace directory resolution. Consumers depend on this API; only
//! backend crates touch SQL or paths.

mod backend;
mod error;
mod num;
mod row;
mod workspace;

pub use backend::StorageBackend;
pub use error::{Error, Result};
pub use num::PaperNum;
pub use row::{PaperRow, decode_authors};
pub use workspace::{WORKSPACE_ENV_VAR, default_workspace_dir};
