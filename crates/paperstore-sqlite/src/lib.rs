//! SQLite backend for the `paperstore` abstract storage API.
//!
//! Port of the read slice of the Python `paperstore.sqlite_backend`: opens
//! `<workspace_dir>/paperstore.db`, ensures the `papers` schema, and
//! implements [`paperstore::StorageBackend`] against it.

mod backend;
mod schema;

pub use backend::SqliteBackend;
