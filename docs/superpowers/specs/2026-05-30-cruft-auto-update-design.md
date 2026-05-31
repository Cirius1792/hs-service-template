# Cruft Auto-Update Workflow — Design Spec

**Date:** 2026-05-30
**Status:** Approved

## Goal

Every downstream repo generated from this template detects when the template has
new commits, re-renders the template with the downstream's saved variables, and
opens a pull request on Gitea for the maintainer to review and merge.

## Context

- Downstream repos are created via `cruft create`, not `cookiecutter` directly.
- Each downstream repo already contains a `.cruft.json` that records the template
  commit hash and all template variable answers.
- Downstream repos live on **Gitea** (`gitea.cltec.dev`).
- The existing `GIT_TOKEN` secret (already used by Portainer workflows) is a
  Gitea personal access token with `issue:read, repository:write` scope —
  sufficient for PR creation. No new secret is needed.
- A previous attempt (commit `0d8c508`) used `peter-evans/create-pull-request` and
  was removed because that action does not support Gitea.

## Architecture

A single self-contained Gitea Actions workflow, generated inside every downstream
repo by the template:

```text
[cron: weekly / workflow_dispatch]
        │
        ▼
  cruft check          ←── compares .cruft.json hash to template HEAD
        │
        ▼ (exit 1 = changes)
  cruft update          ←── re-renders template with downstream variables
        │
        ▼
  git push cruft/update --force
        │
        ▼
  curl POST Gitea API   ←── creates PR (handles 409 = already exists)
```

## Files

| File | Action |
|---|---|
| `{{cookiecutter.repository_name}}/.github/workflows/cruft-update.yml` | **Create** — the workflow |
| `{{cookiecutter.repository_name}}/README.md` | **Modify** — add "Template auto-updates" section |
| `README.md` (template root) | **Modify** — note cruft auto-update in Philosophy/CI section |
| `tests/test_template.py` | **Modify** — add assertions for the new workflow |

## Workflow specification

### Triggers

- `schedule`: `0 3 * * 1` (every Monday at 3am UTC)
- `workflow_dispatch`: manual trigger for ad-hoc runs

### Permissions

- `contents: write` — needed to push the `cruft/update` branch

No `pull-requests: write` is needed since PR creation goes through the Gitea API
directly, authenticated by `GIT_TOKEN`.

### Steps

1. **Checkout** — `actions/checkout@v4`
2. **Setup Python** — `actions/setup-python@v5` with Python 3.11
3. **Install cruft** — `pip install cruft`
4. **Check for updates** — `cruft check`; sets `has_changes` output
5. **Apply updates** — `cruft update --skip-apply-ask --refresh-private-variables` (only if `has_changes == 'true'`)
6. **Push branch** — `git checkout -b cruft/update && git push origin cruft/update --force`
7. **Create PR** — `curl` to `POST https://gitea.cltec.dev/api/v1/repos/{owner}/{repo}/pulls`

### PR creation details

- **Endpoint:** `POST /api/v1/repos/${{ gitea.repository }}/pulls`
- **Auth:** `Authorization: token ${{ secrets.GIT_TOKEN }}`
- **Payload:** `{ title, head: "cruft/update", base: "main", body }`
- **HTTP 201:** PR created successfully.
- **HTTP 409:** PR already exists for this head/base pair — skip, no error.
- **Other status codes:** Fail the job.

### Error handling matrix

| Scenario | Behavior |
|---|---|
| No template updates | `cruft check` exits 0 → job stops cleanly |
| Template has new commits | Full flow: update → push → PR |
| PR already open for `cruft/update` | Gitea returns 409 → log and exit 0 |
| No `.cruft.json` in repo | `cruft check` fails → job fails (should not happen) |
| `GIT_TOKEN` missing/invalid | curl 401/403 → job fails |
| Template repo unreachable | `cruft check` fails → job fails |
| Merge conflict during `cruft update` | cruft fails → job fails (human needed) |

### Secrets

| Secret | Used by | Already exists? |
|---|---|---|
| `GIT_TOKEN` | Create PR on Gitea | Yes (Portainer workflows) |

## Downstream customisation

Downstream repos can skip files from updates by editing `.cruft.json`:

```json
{
  "skip": ["docker-compose.yml", "stack.env"]
}
```

Or via `pyproject.toml`:

```toml
[tool.cruft]
skip = ["docker-compose.yml", "stack.env"]
```

## Testing

Add to `tests/test_template.py`:

- `test_cruft_workflow_exists()` — assert the workflow file is generated in the
  rendered output
- `test_cruft_workflow_triggers()` — verify `schedule` and `workflow_dispatch`
  are present
- `test_cruft_workflow_uses_gitea_api()` — assert the endpoint URL is
  `gitea.cltec.dev`

## Out of scope

- Dual-PR (accept/reject) pattern — adds complexity for no homelab value
- Centralized workflow in template repo — downstream repos already have the token
  and infrastructure; running locally keeps things decoupled
- Renovate/Dependabot integration — unrelated to template sync
