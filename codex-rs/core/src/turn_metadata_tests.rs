use super::*;

use serde_json::Value;
use tempfile::TempDir;
use tokio::process::Command;

/// Decodes the Base64-encoded x-codex-turn-metadata header value.
fn decode_turn_metadata_header(header: &str) -> String {
    use base64::prelude::*;
    BASE64_STANDARD
        .decode(header)
        .map_err(|e| format!("Failed to decode base64: {}", e))
        .and_then(|bytes| String::from_utf8(bytes).map_err(|e| e.to_string()))
        .expect("x-codex-turn-metadata should be valid Base64-encoded UTF-8")
}

#[tokio::test]
async fn build_turn_metadata_header_includes_has_changes_for_clean_repo() {
    let temp_dir = TempDir::new().expect("temp dir");
    let repo_path = temp_dir.path().join("repo");
    std::fs::create_dir_all(&repo_path).expect("create repo");

    Command::new("git")
        .args(["init"])
        .current_dir(&repo_path)
        .output()
        .await
        .expect("git init");
    Command::new("git")
        .args(["config", "user.name", "Test User"])
        .current_dir(&repo_path)
        .output()
        .await
        .expect("git config user.name");
    Command::new("git")
        .args(["config", "user.email", "test@example.com"])
        .current_dir(&repo_path)
        .output()
        .await
        .expect("git config user.email");

    std::fs::write(repo_path.join("README.md"), "hello").expect("write file");
    Command::new("git")
        .args(["add", "."])
        .current_dir(&repo_path)
        .output()
        .await
        .expect("git add");
    Command::new("git")
        .args(["commit", "-m", "initial"])
        .current_dir(&repo_path)
        .output()
        .await
        .expect("git commit");

    let header = build_turn_metadata_header(&repo_path, Some("none"))
        .await
        .expect("header");
    let decoded = decode_turn_metadata_header(&header);
    let parsed: Value = serde_json::from_str(&decoded).expect("valid json");
    let workspace = parsed
        .get("workspaces")
        .and_then(Value::as_object)
        .and_then(|workspaces| workspaces.values().next())
        .cloned()
        .expect("workspace");

    assert_eq!(
        workspace.get("has_changes").and_then(Value::as_bool),
        Some(false)
    );
}

#[test]
fn turn_metadata_state_uses_platform_sandbox_tag() {
    let temp_dir = TempDir::new().expect("temp dir");
    let cwd = temp_dir.path().to_path_buf();
    let sandbox_policy = SandboxPolicy::new_read_only_policy();

    let state = TurnMetadataState::new(
        "session-a".to_string(),
        "turn-a".to_string(),
        cwd,
        &sandbox_policy,
        WindowsSandboxLevel::Disabled,
    );

    let header = state.current_header_value().expect("header");
    let decoded = decode_turn_metadata_header(&header);
    let json: Value = serde_json::from_str(&decoded).expect("json");
    let sandbox_name = json.get("sandbox").and_then(Value::as_str);
    let session_id = json.get("session_id").and_then(Value::as_str);

    let expected_sandbox = sandbox_tag(&sandbox_policy, WindowsSandboxLevel::Disabled);
    assert_eq!(sandbox_name, Some(expected_sandbox));
    assert_eq!(session_id, Some("session-a"));
}
