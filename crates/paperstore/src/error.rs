//! Error and result types for paperstore operations.

use crate::num::PaperNum;

/// Errors returned by paperstore operations.
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum Error {
    /// A string did not have the shape of a WG21 paper number.
    #[error("{0:?} is not a paper number")]
    #[non_exhaustive]
    BadPaperNum(String),

    /// No metadata row exists for the paper.
    #[error("no metadata for paper {0}")]
    #[non_exhaustive]
    MissingPaper(PaperNum),

    /// The paper has no converted markdown.
    #[error("no converted markdown for paper {0}")]
    #[non_exhaustive]
    MissingMarkdown(PaperNum),

    /// `WG21_DATA_DIR` is unset or empty.
    #[error(
        "WG21_DATA_DIR is not set. Set it to the directory where paperflow stores its data.\n  export WG21_DATA_DIR=/path/to/wg21-data"
    )]
    WorkspaceEnvUnset,

    /// An underlying I/O error.
    #[error(transparent)]
    #[non_exhaustive]
    Io(#[from] std::io::Error),

    /// An error reported by a concrete storage backend driver, boxed so the
    /// abstract API stays free of backend types.
    #[error(transparent)]
    #[non_exhaustive]
    Backend(#[from] Box<dyn std::error::Error + Send + Sync>),
}

impl Error {
    /// Returns [`Error::MissingPaper`] for `num`.
    ///
    /// Backend crates construct this variant through here, since the variant
    /// is `#[non_exhaustive]` and cannot be built literally downstream.
    #[must_use]
    pub fn missing_paper(num: PaperNum) -> Self {
        Self::MissingPaper(num)
    }

    /// Returns [`Error::MissingMarkdown`] for `num`.
    ///
    /// Backend crates construct this variant through here, since the variant
    /// is `#[non_exhaustive]` and cannot be built literally downstream.
    #[must_use]
    pub fn missing_markdown(num: PaperNum) -> Self {
        Self::MissingMarkdown(num)
    }
}

/// Result alias for paperstore operations.
pub type Result<T> = std::result::Result<T, Error>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn error_is_send_sync_and_static() {
        fn assert_bounds<T: Send + Sync + 'static>() {}
        assert_bounds::<Error>();
    }

    #[test]
    fn missing_paper_constructor_builds_missing_paper() {
        let num = PaperNum::parse("P4003R2").unwrap_or_else(|e| panic!("{e}"));
        match Error::missing_paper(num.clone()) {
            Error::MissingPaper(carried) => assert_eq!(carried, num),
            other => panic!("expected MissingPaper, got {other:?}"),
        }
    }

    #[test]
    fn missing_markdown_constructor_builds_missing_markdown() {
        let num = PaperNum::parse("N4950").unwrap_or_else(|e| panic!("{e}"));
        match Error::missing_markdown(num.clone()) {
            Error::MissingMarkdown(carried) => assert_eq!(carried, num),
            other => panic!("expected MissingMarkdown, got {other:?}"),
        }
    }
}
