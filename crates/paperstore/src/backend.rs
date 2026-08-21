//! The abstract storage backend trait.

use crate::error::Result;
use crate::num::PaperNum;
use crate::row::PaperRow;

/// Abstract storage interface for paperflow artifacts.
///
/// Port of the Python `StorageBackend` ABC, reduced to the read slice the
/// Rust workspace needs. Consumers depend on this trait; only backend
/// crates touch SQL or paths.
pub trait StorageBackend {
    /// Returns the metadata row for `num`.
    ///
    /// # Errors
    ///
    /// Returns [`crate::Error::MissingPaper`] when no row exists for `num`.
    fn meta(&self, num: &PaperNum) -> Result<PaperRow>;

    /// Returns the converted markdown for `num`.
    ///
    /// # Errors
    ///
    /// Returns [`crate::Error::MissingMarkdown`] when the paper has no
    /// converted markdown.
    fn paper_md(&self, num: &PaperNum) -> Result<String>;
}
