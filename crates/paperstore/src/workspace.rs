//! Workspace directory resolution from the environment.

use std::path::PathBuf;

use crate::error::{Error, Result};

/// Environment variable naming the paperflow data directory.
pub const WORKSPACE_ENV_VAR: &str = "WG21_DATA_DIR";

/// Resolves the workspace path from `$WG21_DATA_DIR`.
///
/// The value is trimmed; the resolved path is not required to exist.
///
/// # Errors
///
/// Returns [`Error::WorkspaceEnvUnset`] when the variable is unset or empty
/// after trimming.
pub fn default_workspace_dir() -> Result<PathBuf> {
    let value = std::env::var(WORKSPACE_ENV_VAR).unwrap_or_default();
    let trimmed = value.trim();
    if trimmed.is_empty() {
        Err(Error::WorkspaceEnvUnset)
    } else {
        Ok(PathBuf::from(trimmed))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // One test function: env-mutating cases must not run in parallel.
    #[test]
    fn default_workspace_dir_env_cases() {
        temp_env::with_var_unset(WORKSPACE_ENV_VAR, || {
            assert!(matches!(
                default_workspace_dir(),
                Err(Error::WorkspaceEnvUnset)
            ));
        });
        temp_env::with_var(WORKSPACE_ENV_VAR, Some(""), || {
            assert!(matches!(
                default_workspace_dir(),
                Err(Error::WorkspaceEnvUnset)
            ));
        });
        temp_env::with_var(WORKSPACE_ENV_VAR, Some("   "), || {
            assert!(matches!(
                default_workspace_dir(),
                Err(Error::WorkspaceEnvUnset)
            ));
        });
        temp_env::with_var(WORKSPACE_ENV_VAR, Some(" /data/wg21 "), || {
            assert_eq!(
                default_workspace_dir().ok(),
                Some(PathBuf::from("/data/wg21"))
            );
        });
    }

    #[test]
    fn workspace_env_unset_message_names_variable_with_export_hint() {
        temp_env::with_var_unset(WORKSPACE_ENV_VAR, || {
            let message = default_workspace_dir()
                .err()
                .map(|e| e.to_string())
                .unwrap_or_default();
            assert!(
                message.contains("WG21_DATA_DIR") && message.contains("export WG21_DATA_DIR="),
                "unexpected message: {message}"
            );
        });
    }
}
