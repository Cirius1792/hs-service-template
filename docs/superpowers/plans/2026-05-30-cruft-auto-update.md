# Cruft Auto-Update Workflow — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `cruft-update.yml` workflow to every generated downstream repo that detects template changes, applies them, and opens a PR on Gitea.

**Architecture:** Single self-contained Gitea Actions workflow placed by the Cookiecutter template. Uses `cruft check`/`cruft update` for detection and re-rendering, then `curl` to the Gitea API for PR creation. Reuses existing `GIT_TOKEN` secret. No new Cookiecutter variables or secrets needed.

**Tech Stack:** cruft (pip), Gitea API (curl), actions/checkout@v6, actions/setup-python@v6

**Spec:** `docs/superpowers/specs/2026-05-30-cruft-auto-update-design.md`

---

## File structure

| Action | Path |
|---|---|
| Create | `{{cookiecutter.repository_name}}/.github/workflows/cruft-update.yml` |
| Modify | `{{cookiecutter.repository_name}}/README.md` |
| Modify | `README.md` (template root) |
| Modify | `tests/test_template.py` |

---

## Chunk 1: Create the cruft-update workflow

### Task 1: Create `{{cookiecutter.repository_name}}/.github/workflows/cruft-update.yml`

**Files:**
- Create: `{{cookiecutter.repository_name}}/.github/workflows/cruft-update.yml`

- [ ] **Step 1: Write the workflow file**

```yaml
name: Cruft template update

on:
  schedule:
    - cron: "0 3 * * 1"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  cruft-update:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v6

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.11"

      - name: Install cruft
        run: pip install cruft

      - name: Check for template updates
        id: check
        run: |
          set -e
          if cruft check; then
            echo "has_changes=false" >> "$GITHUB_OUTPUT"
          else
            echo "has_changes=true" >> "$GITHUB_OUTPUT"
          fi

      - name: Apply template updates
        if: steps.check.outputs.has_changes == 'true'
        run: |
          set -e
          git config user.name "cruft-bot"
          git config user.email "cruft-bot@cltec.dev"
          cruft update --skip-apply-ask --refresh-private-variables

      - name: Push update branch
        if: steps.check.outputs.has_changes == 'true'
        run: |
          set -e
          git checkout -b cruft/update
          git push origin cruft/update --force

      - name: Create PR on Gitea
        if: steps.check.outputs.has_changes == 'true'
        env:
          GITEA_TOKEN: {{ '${{ secrets.GIT_TOKEN }}' }}
        run: |
          {% raw %}
          set -e

          RESPONSE=$(curl -sS -w "\n%{http_code}" -X POST \
            "https://gitea.cltec.dev/api/v1/repos/${{ gitea.repository }}/pulls" \
            -H "Authorization: token $GITEA_TOKEN" \
            -H "Content-Type: application/json" \
            -d "$(cat <<'BODY'
          {
            "title": "chore: template update via cruft",
            "head": "cruft/update",
            "base": "main",
            "body": "Automated update from the [hs-service-template](https://gitea.cltec.dev/clt/hs-service-template).\n\nReview the changes and merge to accept, or close to reject."
          }
          BODY
          )")

          HTTP_STATUS=$(printf '%s\n' "$RESPONSE" | tail -n1)

          case "$HTTP_STATUS" in
            201) echo "PR created successfully." ;;
            409) echo "PR already exists for branch cruft/update — skipping." ;;
            *)
              echo "Unexpected HTTP status: $HTTP_STATUS"
              printf '%s\n' "$RESPONSE" | sed '$d'
              exit 1
              ;;
          esac
          {% endraw %}
```

**⚠️ Jinja escaping notes:**
- `{{ '${{ secrets.GIT_TOKEN }}' }}` — Cookiecutter processes this once, emitting `${{ secrets.GIT_TOKEN }}` for Gitea Actions
- `{% raw %}...{% endraw %}` wraps the multi-line shell block containing `${{ gitea.repository }}`
- `<<'BODY'` — single-quoted heredoc delimiter prevents shell expansion inside the JSON body
- `$GITEA_TOKEN` is a shell variable (set from `env:`), does not need escaping
- `$GITHUB_OUTPUT` is fine (single `$`)

- [ ] **Step 2: Verify the file exists**

```bash
test -f "{{cookiecutter.repository_name}}/.github/workflows/cruft-update.yml" && echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add "{{cookiecutter.repository_name}}/.github/workflows/cruft-update.yml"
git commit -m "feat: add cruft auto-update workflow for downstream repos"
```

---

## Chunk 2: Update the generated README

### Task 2: Add template auto-updates section to generated README

**Files:**
- Modify: `{{cookiecutter.repository_name}}/README.md`

- [ ] **Step 1: Append the section before the "Configuration deployment workflow" heading**

Insert after the "Monitoring" section (before "## Configuration deployment workflow"):

```markdown
## Template auto-updates

This repository includes a weekly workflow (`.github/workflows/cruft-update.yml`) that checks
for updates to the upstream [hs-service-template](https://gitea.cltec.dev/clt/hs-service-template).
When new template changes are detected, `cruft` re-renders the template with this project's
saved variables and opens a pull request for review.

- **Schedule:** every Monday at 3am UTC
- **Manual trigger:** available via `workflow_dispatch` in the Actions tab
- **Authentication:** reuses the existing `GIT_TOKEN` secret

### Skipping files from updates

To prevent cruft from updating specific files, add them to the `skip` list in
`.cruft.json`:

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
```

- [ ] **Step 2: Verify the section was added**

```bash
grep -q "Template auto-updates" "{{cookiecutter.repository_name}}/README.md" && echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add "{{cookiecutter.repository_name}}/README.md"
git commit -m "docs: document cruft auto-update in generated README"
```

---

## Chunk 3: Update the template root README

### Task 3: Add cruft note to root README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a bullet point to the Philosophy section**

The Philosophy section currently reads:
```
- Git is the source of truth; no manual changes on servers.
- All configuration is expressed as code and validated with portable tooling.
- Reverse proxy automation is opt-in and safe by default.
- No secrets committed—environment variables live in `.env` or CI secrets.
```

Add after the last bullet:

```markdown
- Template auto-updates via [cruft](https://cruft.github.io/cruft/) keep every
  generated repo in sync with template improvements. A weekly Gitea Action
  detects changes, re-renders the template, and opens a pull request for review.
```

- [ ] **Step 2: Verify**

```bash
grep -q "cruft" README.md && echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: note cruft auto-update capability in root README"
```

---

## Chunk 4: Add tests

### Task 4: Add test cases to `tests/test_template.py`

**Files:**
- Modify: `tests/test_template.py`

- [ ] **Step 1: Add test for workflow file existence**

Append to `tests/test_template.py`:

```python
def test_cruft_workflow_exists(tmp_path: Path) -> None:
    """The cruft-update workflow is generated in every rendered project."""
    project = render_project(tmp_path)

    workflow = project / ".github/workflows/cruft-update.yml"
    assert workflow.is_file(), "cruft-update.yml should be rendered"

    content = workflow.read_text()
    assert "{{ cookiecutter" not in content, (
        "No raw Cookiecutter placeholders should remain"
    )
    assert "{%" not in content, "No raw Jinja tags should remain"


def test_cruft_workflow_triggers(tmp_path: Path) -> None:
    """The workflow has both schedule and manual triggers."""
    project = render_project(tmp_path)
    workflow = project / ".github/workflows/cruft-update.yml"
    content = workflow.read_text()

    assert "schedule:" in content, "Must have scheduled trigger"
    assert "cron:" in content, "Must have cron schedule"
    assert "workflow_dispatch" in content, "Must have manual trigger"


def test_cruft_workflow_targets_gitea(tmp_path: Path) -> None:
    """The PR creation step uses the correct Gitea API endpoint."""
    project = render_project(tmp_path)
    workflow = project / ".github/workflows/cruft-update.yml"
    content = workflow.read_text()

    assert "gitea.cltec.dev" in content, (
        "Must target gitea.cltec.dev API"
    )
    assert "api/v1/repos" in content, (
        "Must use Gitea API v1"
    )


def test_cruft_workflow_reuses_git_token(tmp_path: Path) -> None:
    """The workflow uses GIT_TOKEN, not a new secret."""
    project = render_project(tmp_path)
    workflow = project / ".github/workflows/cruft-update.yml"
    content = workflow.read_text()

    assert "secrets.GIT_TOKEN" in content, (
        "Must reuse existing GIT_TOKEN secret"
    )
    assert "secrets.GITEA_TOKEN" not in content, (
        "Must not reference a separate GITEA_TOKEN secret"
    )
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
cd /home/clt/PersonalProjects/hs-service-template && python -m pytest tests/test_template.py -v
```

Expected: all tests pass (4 new + 2 existing = 6 total)

> **Note:** If the workflow file doesn't exist yet, the test WILL fail at this point.
> Run the test after writing the workflow file (Task 1), or skip and run all
> together at the validation step.

- [ ] **Step 3: Commit**

```bash
git add tests/test_template.py
git commit -m "test: add assertions for cruft auto-update workflow"
```

---

## Chunk 5: Full validation

### Task 5: Run complete validation

- [ ] **Step 1: Run the full test suite**

```bash
cd /home/clt/PersonalProjects/hs-service-template && python -m pytest tests/test_template.py -v
```

Expected output: 6 tests pass (2 existing + 4 new)

- [ ] **Step 2: Render the template locally and inspect the output**

```bash
cd /tmp && rm -rf test-cruft-render && \
cookiecutter --no-input \
  --output-dir /tmp/test-cruft-render \
  /home/clt/PersonalProjects/hs-service-template \
  service_name=testcruft \
  repository_name=test-cruft-service \
  service_group=Tools \
  service_icon=gear \
  base_domain=example.com \
  default_port=8080 \
  include_proxy_config=y
```

- [ ] **Step 3: Verify rendered output**

```bash
# Check workflow file exists
test -f /tmp/test-cruft-render/test-cruft-service/.github/workflows/cruft-update.yml && echo "OK: workflow"

# Check no raw Cookiecutter placeholders in rendered output
grep -c "cookiecutter" /tmp/test-cruft-render/test-cruft-service/.github/workflows/cruft-update.yml
# Should show 0 (no raw placeholders left)

# Check README has auto-update section
grep -q "Template auto-updates" /tmp/test-cruft-render/test-cruft-service/README.md && echo "OK: readme"
```

- [ ] **Step 4: Clean up**

```bash
rm -rf /tmp/test-cruft-render
```

- [ ] **Step 5: Commit if anything was missed**

```bash
git status
# Should show clean working tree — if not, add and commit remaining changes
```

---

## Summary of commits

| Order | Message | Files |
|---|---|---|
| 1 | `feat: add cruft auto-update workflow for downstream repos` | `{{cookiecutter.repository_name}}/.github/workflows/cruft-update.yml` |
| 2 | `docs: document cruft auto-update in generated README` | `{{cookiecutter.repository_name}}/README.md` |
| 3 | `docs: note cruft auto-update capability in root README` | `README.md` |
| 4 | `test: add assertions for cruft auto-update workflow` | `tests/test_template.py` |
