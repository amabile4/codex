# Azure Fork Release Notes: `azure/release-0.117.0`

## Scope

This document describes fork-only changes applied on top of the upstream
release tag `rust-v0.117.0`.

- Base version: `openai/codex@rust-v0.117.0`
- Fork branch: `azure/release-0.117.0`
- Scope: `codex-rs/core/**` only
- Diff summary: 8 files changed, 123 insertions, 44 deletions

Related commits:
- `0ebe41f3b` - core: apply 0.116 turn-metadata base64 patch
- `2360a3d5e` - core: decode turn metadata before MCP meta parsing

---

## Why this fork patch exists

This patch addresses Azure compatibility issues related to
`x-codex-turn-metadata` handling (see `openai/codex#13232`).

Upstream `rust-v0.117.0` does not fully preserve the fork behavior required
for safe handling of `x-codex-turn-metadata` across all environments.

In particular, some HTTP infrastructures may reject non-ASCII header values.
Previous implementations allowed raw JSON to be passed at transport
boundaries, which can fail in such environments.

This fork standardizes the following contract:

> `x-codex-turn-metadata` is Base64-encoded JSON at transport boundaries,
> while all internal logic continues to operate on decoded JSON objects.

---

## Functional changes

### 1) Header boundary contract tightened (`core/src/client.rs`)

- `parse_turn_metadata_header` now accepts metadata values only if:
  - the value is valid Base64, and
  - the value is a valid HTTP header string.
- Raw (non-Base64) JSON is no longer forwarded as header metadata.

This ensures that only ASCII-safe values cross HTTP and WebSocket boundaries.

---

### 2) Turn metadata generation standardized (`core/src/turn_metadata.rs`)

- `TurnMetadataBag::to_header_value` now:
  - serializes metadata to JSON, then
  - Base64-encodes the result before emitting a header value.
- `TurnMetadataState::current_meta_value` now:
  - decodes Base64,
  - validates UTF-8, and
  - parses JSON for internal consumers.

This closes a mismatch where internal code previously attempted to parse
JSON directly from encoded header text.

---

### 3) MCP metadata path aligned (`core/src/mcp_tool_call_tests.rs`)

- MCP-related tests now derive expected metadata via
  `TurnMetadataState::current_meta_value()`.
- This reflects the real runtime contract:
  decoded JSON is consumed internally, regardless of transport encoding.

---

## Test coverage updates

The following test suites were updated or extended to reflect the new contract:

- `core/src/client_tests.rs`
- `core/src/turn_metadata_tests.rs`
- `core/src/mcp_tool_call_tests.rs`
- `core/tests/responses_headers.rs`
- `core/tests/suite/client_websockets.rs`
- `core/tests/suite/turn_state.rs`

Coverage intent:

- Transport-layer headers are always Base64-encoded.
- Raw JSON is rejected at header boundaries.
- Internal consumers observe unchanged JSON structure.
- WebSocket forwarding preserves encoded metadata.

---

## What this patch does not change

- No changes to turn metadata semantics
- No changes to model APIs or protocols
- No changes to MCP behavior or plugin contracts
- No changes to non-core components, CI, or tooling

This patch is strictly a transport-safety fix.

---

## Validation notes

- Previously failing tests now pass when executed directly:
  - `mcp_tool_call_request_meta_includes_turn_metadata_for_custom_server`
  - `codex_apps_tool_call_request_meta_includes_turn_metadata_and_codex_apps_meta`
- Full `cargo test -p codex-core` execution on Windows may still encounter
  environment-dependent failures unrelated to this patch
  (for example missing local test binaries or local filesystem conditions).

---

## Artifacts

- A human-readable diff against upstream is provided at:
  - `azure-release-0.117.0-vs-rust-v0.117.0.diff`

---

## Release process note

This repository operates with restricted PR privileges.
When upstream PR submission is not feasible, this branch and document
serve as the auditable release record.
