# Releasing (Fork Maintenance Guide)

This document describes the standard procedure for tracking upstream releases
of `openai/codex` in this fork and reapplying the Azure compatibility patch
related to issue #13232.

This fork intentionally keeps `main` identical to upstream and applies a
minimal, repeatable patch only on release branches.

---

## Scope

- Fork: amabile4/codex
- Upstream: openai/codex
- Patch purpose: Base64-encode x-codex-turn-metadata HTTP header
- Related issue: https://github.com/openai/codex/issues/13232
- Supported workflow: tag-based releases only (no alpha/beta/rc)

---

## Prerequisites (one-time setup)

Enable git rerere so conflict resolutions are reused automatically:

git config --global rerere.enabled true
git config --global rerere.autoupdate true

Verify:

git config --global --get rerere.enabled

Expected output:

true

---

## Release Tracking Policy

- main must always be a clean mirror of upstream/main
- No patches are applied directly to main
- Each upstream release tag gets its own branch:

azure/release-X.Y.Z

---

## Step-by-Step: Handling a New Upstream Release

1. Sync main with upstream

   git checkout main
   git fetch upstream --tags
   git reset --hard upstream/main
   git push --force origin main

2. Identify the official release tag (example: 0.117.0)

   git tag | grep '^rust-v0\.117\.0$'

3. Create a release branch from the tag

   git checkout -b azure/release-0.117.0 rust-v0.117.0

4. Reapply the Azure compatibility patch

   git cherry-pick <PATCH_COMMIT_HASH>

   If a conflict occurs:

   git add .
   git cherry-pick --continue

5. Verify the diff

   git diff rust-v0.117.0..HEAD

6. Build verification (recommended on WSL2)

   cd codex-rs
   cargo build
   cargo build --release

7. Push the release branch

   git push -u origin azure/release-0.117.0

---

## Notes on Patch Storage

- The Azure compatibility patch must remain a single commit
- Do not apply raw .patch files for future releases
- Always reuse the same commit via cherry-pick

---

## Quick Reference

main                     -> mirror of upstream/main
azure/release-X.Y.Z      -> upstream tag + Azure patch

PATCH COMMIT: <PATCH_COMMIT_HASH>
FIRST APPLIED: rust-v0.116.0