//! paper-mcp: an MCP server that gives prompts full access to WG21 papers,
//! their metadata, text, citations, and search, all served from Qdrant.
//!
//! `paper-mcp ingest` copies the paperstore into Qdrant; `paper-mcp serve`
//! answers MCP calls from Qdrant alone.

pub mod bm25;
pub mod config;
pub mod dates;
pub mod paper_id;
pub mod text;
