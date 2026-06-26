---
name: release
description: Bump version in pyproject files, tag, push, and create a GitHub release with notes drafted from commits since the last tag.
disable-model-invocation: true
argument-hint: "[major|minor|patch|<explicit version>]"
---

# Cut a Release

Bump the version, tag, push, and create a GitHub release.

## Steps

1. **Resolve and preview the bump.** The argument is `major`, `minor`, `patch`, or an explicit `X.Y.Z` (ask the user if absent). Dry-run the bumper to see the before/after table for every `pyproject.toml`, the new version, the previous tag, and any drift warning:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/bump_versions.py" <arg>
   ```
   The script uses the latest git tag (`git describe --tags --abbrev=0`) as the previous version, so it also handles step 2's tag-vs-root drift check: if the root `pyproject.toml` disagrees with the latest tag, it prints a `DRIFT:` line and computes the bump from the tag. No `v` prefix in `pyproject.toml`; the `v` prefix goes on the git tag.

2. **Sanity checks before touching anything.**
   - `git status --porcelain` must be empty. If not, stop and ask.
   - Determine the canonical remote: if `git remote get-url upstream` succeeds, use `upstream`; otherwise use `origin`. Use this remote for all push/fetch in this skill (the user's `origin` is often a personal fork).
   - Current branch should be `main` and up to date with `<remote>/main`. If not, stop and ask.
   - `git tag -l v<new>` must be empty. If the tag exists, stop.
   - Surface any `DRIFT:` warning from step 1 to the user.

3. **Bump versions.** Show the user the before/after table from step 1, then apply it. The script rewrites `version = "..."` in the root `pyproject.toml` and every `packages/*/pyproject.toml`:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/bump_versions.py" <arg> --apply
   ```
   If a package was intentionally on a different track, the user will say so explicitly; otherwise everything syncs to the root version.

4. **Run the workspace `uv sync`** to refresh `uv.lock`, then run tests per-package the way CI does (a single root `uv run pytest` collides on duplicate test module basenames). Discover packages from disk so the loop never drifts out of sync with `packages/` (a hardcoded list silently skips new packages):
   ```
   uv sync
   for dir in packages/*/tests; do
     [ -d "$dir" ] || continue
     uv run pytest "$dir" -q || exit 1
   done
   uv run pytest tests -q
   ```
   If anything fails, stop.

5. **Draft release notes.** Collect input from:
   - `git log --oneline <prev-tag>..HEAD`
   - `gh pr list --state merged --search "merged:>$(git log -1 --format=%cI <prev-tag>)" --limit 50` for PR titles + authors.

   Produce a markdown body matching the project's style (see `gh release view <prev-tag>` for the most recent example). At minimum:
   ```
   ## v<new>

   <one-paragraph summary>

   ### Highlights
   - ...

   ## What's Changed
   * <PR title> by @<author> in <PR url>

   **Full Changelog**: https://github.com/<owner>/<repo>/compare/v<prev>...v<new>
   ```
   Show the draft to the user and wait for approval before continuing.

6. **Commit, tag, push.** After approval (use the remote chosen in step 2):
   ```
   git add pyproject.toml packages/*/pyproject.toml uv.lock
   git commit -m "Release v<new>"
   git tag -a v<new> -m "v<new>"
   git push <remote> main
   git push <remote> v<new>
   ```

7. **Create the release.**
   ```
   gh release create v<new> --title "v<new>" --notes-file <tmpfile>
   ```
   Then print the release URL from `gh release view v<new> --json url -q .url`.

## Rules

- Never force-push. Never delete a tag without explicit user instruction.
- If a step fails partway through (e.g. push rejected), stop and surface the error. Do not auto-revert the version bump commit.
- Respect the project style guide: no em dashes in commit messages or release notes.
- This repo's release triggers a downstream `notify-superproject-vendor-pin` workflow on `release.published`. Mention this to the user after the release is created so they can verify the dispatch ran.
