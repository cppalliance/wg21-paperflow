//! Paper metadata rows and author-list decoding.

/// A metadata row for one paper, mirroring the Python `PaperRow` dataclass.
///
/// `authors` is always a decoded list (see [`decode_authors`]);
/// `source_file` and `markdown_path` are empty strings when the
/// corresponding artifact has not been staged.
#[derive(Clone, Debug, Default)]
pub struct PaperRow {
    /// Uppercase paper number, as stored.
    pub paper_num: String,
    /// Mailing year (e.g. `"2026"`).
    pub year: String,
    /// Paper title.
    pub title: String,
    /// Target subgroup (e.g. `"LEWG"`).
    pub target_group: String,
    /// YAML-front-matter intent signal from conversion.
    pub intent: String,
    /// Canonical URL.
    pub url: String,
    /// Document date, as recorded.
    pub document_date: String,
    /// Mailing date (`YYYY-MM`), as recorded.
    pub mailing_date: String,
    /// Disposition, as recorded.
    pub disposition: String,
    /// Previous version's paper number, or empty.
    pub previous_version: String,
    /// Staged source file path, or empty when not staged.
    pub source_file: String,
    /// Converted markdown path, or empty when not converted.
    pub markdown_path: String,
    /// Deprecated upstream; kept for parity.
    pub dissect_path: String,
    /// Agora JSON artifact path, or empty.
    pub agora_path: String,
    /// Assay report path, or empty.
    pub assay_path: String,
    /// Timestamp of the last citation extraction, or empty.
    pub citations_extracted_at: String,
    /// Last recorded pipeline error, or empty.
    pub error: String,
    /// Author names, decoded from storage by [`decode_authors`].
    pub authors: Vec<String>,
    /// Line count of the converted markdown.
    pub line_count: u64,
    /// Pipeline status code.
    pub status: i64,
}

/// Deserializes an authors value from storage into a list of names.
///
/// Port of `parse_authors_raw` from the Python `paperstore.backend`:
///
/// - Empty or whitespace-only input yields an empty list.
/// - A JSON array of strings decodes as that array.
/// - Anything else splits on commas, with each element trimmed and empties
///   dropped.
#[must_use]
pub fn decode_authors(raw: &str) -> Vec<String> {
    if raw.trim().is_empty() {
        return Vec::new();
    }
    if raw.starts_with('[')
        && let Ok(authors) = serde_json::from_str::<Vec<String>>(raw)
    {
        return authors;
    }
    raw.split(',')
        .map(str::trim)
        .filter(|a| !a.is_empty())
        .map(str::to_owned)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn decode_authors_decodes_json_array() {
        assert_eq!(
            decode_authors(r#"["Alice Liddell","Bob Carroll"]"#),
            vec!["Alice Liddell".to_owned(), "Bob Carroll".to_owned()]
        );
        assert_eq!(decode_authors("[]"), Vec::<String>::new());
    }

    #[test]
    fn decode_authors_splits_on_commas() {
        assert_eq!(
            decode_authors("Alice Liddell, Bob Carroll ,,  Carol Danvers "),
            vec![
                "Alice Liddell".to_owned(),
                "Bob Carroll".to_owned(),
                "Carol Danvers".to_owned(),
            ]
        );
    }

    #[test]
    fn decode_authors_empty_and_whitespace_give_empty() {
        assert_eq!(decode_authors(""), Vec::<String>::new());
        assert_eq!(decode_authors("   \t "), Vec::<String>::new());
    }

    #[test]
    fn decode_authors_invalid_json_falls_back_to_comma_split() {
        assert_eq!(decode_authors("[not json"), vec!["[not json".to_owned()]);
    }
}
