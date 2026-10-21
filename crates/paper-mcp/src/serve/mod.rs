//! The serve command (§9): MCP over stateless Streamable HTTP, behind
//! bearer-token auth, answering every call from Qdrant.

pub mod auth;

pub use auth::Keys;
