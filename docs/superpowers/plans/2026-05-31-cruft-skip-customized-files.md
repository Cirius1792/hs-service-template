# Cruft Skip Customized Files Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate persistent cruft skip rules in every downstream repo so `cruft update` leaves post-generation customization files untouched.

**Architecture:** Add a minimal generated `pyproject.toml` containing only `[tool.cruft].skip`, update the generated README to document customization ownership and manual update expectations, and extend the existing Cookiecutter render tests to assert the policy is present. Verify with render-level tests and, if the harness allows, an end-to-end `uvx cruft create/update` acceptance check.

**Tech Stack:** Cookiecutter template, cruft, Python 3.12 test runner, pytest, `tomllib` for TOML parsing.

---

## Spec

Approved spec: `docs/superpowers/specs/2026-05-31-cruft-skip-customized-files-design.md`

The spec is already in the service template repo at `/home/clt/PersonalProjects/hs-service-template/docs/superpowers/specs/2026-05-31-cruft-skip-customized-files-design.md`.

## File Structure

- Create `{{cookiecutter.repository_name}}/pyproject.toml`
  - Responsibility: generated downstream cruft configuration only.
  - Must not define Python package metadata, build backend, dependencies, or runtime tooling.
- Modify `{{cookiecutter.repository_name}}/README.md`
  - Responsibility: document that selected files are downstream-owned after creation and skipped by cruft updates.
  - Replace the current generic skip examples with the concrete generated policy.
- Modify `tests/test_template.py`
  - Responsibility: render the template and verify the generated `pyproject.toml` and README documentation.
- No changes to downstream service-specific files in this implementation.

---

## Chunk 1: Add generated cruft skip policy

### Task 1: Generate minimal `pyproject.toml`

**Files:**
- Create: `{{cookiecutter.repository_name}}/pyproject.toml`
- Test: `tests/test_template.py`

- [ ] **Step 1: Create the generated `pyproject.toml`**

Create `{{cookiecutter.repository_name}}/pyproject.toml` with exactly:

```toml
[tool.cruft]
skip = [
  "docker-compose.yml",
  "stack.env",
  "configurations/locations.ini",
  "configurations/data/**",
  "swag/proxy-confs/**",
]
```

- [ ] **Step 2: Sanity-check that the file is only cruft config**

Run:

```bash
grep -n "^\[" '{{cookiecutter.repository_name}}/pyproject.toml'
```

Expected output contains only:

```text
1:[tool.cruft]
```

No `[project]`, `[build-system]`, dependency table, or package metadata should be present.

- [ ] **Step 3: Commit generated policy**

```bash
git add '{{cookiecutter.repository_name}}/pyproject.toml'
git commit -m "feat: add cruft skip policy to generated repos"
```

---

## Chunk 2: Document skipped customization files

### Task 2: Update generated README cruft section

**Files:**
- Modify: `{{cookiecutter.repository_name}}/README.md`
- Test: `tests/test_template.py`

- [ ] **Step 1: Replace the generic skip examples in README**

In `{{cookiecutter.repository_name}}/README.md`, replace the current `### Skipping files from updates` section:

```markdown
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

with:

````markdown
### Files intentionally skipped from template updates

Some generated files are customization points and are owned by this repository after creation. They are excluded from future `cruft update` runs by the `[tool.cruft]` policy in `pyproject.toml`.

Skipped paths:

| Path | Why it is skipped |
|------|-------------------|
| `docker-compose.yml` | Service image, volumes, environment, labels, and networks often diverge from the template. |
| `stack.env` | Runtime stack values are deployment-specific. |
| `configurations/locations.ini` | Remote file destinations are environment-specific. |
| `configurations/data/**` | Versioned service configuration payloads are downstream-owned. |
| `swag/proxy-confs/**` | Proxy routing, headers, auth, and paths may need service-specific changes. |

`pyproject.toml` exists only to hold cruft configuration. It does not make this repository a Python package and does not define runtime dependencies.

When the upstream template changes one of these skipped files, `cruft update` will not apply that change automatically. Manually compare the template version with this repository's customized version and port only the relevant lines, especially for deployment definitions and proxy configuration.

Template-owned automation and documentation that are not listed here, such as workflows, scripts, and README updates, will continue to be updated by `cruft update`.

Existing repositories that were created before this skip policy may also keep the same skip list directly in `.cruft.json` during migration. That duplication is safe; cruft combines both sources.
````

- [ ] **Step 2: Verify README still renders Jinja conditionals correctly**

Inspect the surrounding README Jinja blocks and confirm this replacement does not alter `{% if cookiecutter.include_proxy_config|lower == 'y' %}` or the SWAG documentation below it.

- [ ] **Step 3: Commit README documentation**

```bash
git add '{{cookiecutter.repository_name}}/README.md'
git commit -m "docs: document cruft-skipped customization files"
```

---

## Chunk 3: Extend render tests

### Task 3: Assert generated cruft skip policy

**Files:**
- Modify: `tests/test_template.py`
- Test: `tests/test_template.py`

- [ ] **Step 1: Add TOML import**

Near the imports in `tests/test_template.py`, add:

```python
import tomllib
```

The file already uses `from __future__ import annotations`, and the current test environment uses Python 3.12, so `tomllib` is available in the standard library.

- [ ] **Step 2: Add expected skip constant**

After `BASE_CONTEXT`, add:

```python
EXPECTED_CRUFT_SKIP = [
    "docker-compose.yml",
    "stack.env",
    "configurations/locations.ini",
    "configurations/data/**",
    "swag/proxy-confs/**",
]
```

- [ ] **Step 3: Add test for generated `pyproject.toml`**

Append this test to `tests/test_template.py`:

```python
def test_generated_pyproject_configures_cruft_skip_policy(tmp_path: Path) -> None:
    """Generated repos persist cruft skip rules for customized files."""
    project = render_project(tmp_path)

    pyproject = project / "pyproject.toml"
    assert pyproject.is_file(), "pyproject.toml should be rendered"

    data = tomllib.loads(pyproject.read_text())

    assert data == {
        "tool": {
            "cruft": {
                "skip": EXPECTED_CRUFT_SKIP,
            }
        }
    }
```

- [ ] **Step 4: Add test for README documentation**

Append this test to `tests/test_template.py`:

```python
def test_readme_documents_cruft_skipped_customization_files(tmp_path: Path) -> None:
    """Generated README explains which files cruft intentionally skips."""
    project = render_project(tmp_path)

    readme = (project / "README.md").read_text()

    assert "Files intentionally skipped from template updates" in readme
    assert "pyproject.toml exists only to hold cruft configuration" in readme
    assert "does not make this repository a Python package" in readme
    assert "Manually compare the template version" in readme
    assert "will continue to be updated by `cruft update`" in readme

    for skipped_path in EXPECTED_CRUFT_SKIP:
        assert skipped_path in readme
```

- [ ] **Step 5: Run the targeted tests**

Use the existing environment caveats from the handoff:

```bash
COOKIECUTTER_SITE=/home/clt/.local/share/pipx/venvs/cookiecutter/lib/python3.12/site-packages \
COOKIECUTTER_CONFIG=/tmp/cookiecutter_config.yaml \
PYTHONPATH="$COOKIECUTTER_SITE:$PYTHONPATH" \
python3 -m pytest tests/test_template.py -v
```

Expected: all tests in `tests/test_template.py` pass.

- [ ] **Step 6: Commit tests**

```bash
git add tests/test_template.py
git commit -m "test: assert generated cruft skip policy"
```

---

## Chunk 4: Acceptance verification

### Task 4: Verify cruft behavior end to end if harness allows

**Files:**
- No required source modifications.
- Temporary files only under `/tmp`.

- [ ] **Step 1: Ensure template repo working tree is clean except intentional committed changes**

Run:

```bash
git status --short
```

Expected: only unrelated untracked environment dotfiles may appear. No tracked modifications should remain.

- [ ] **Step 2: Create a temporary branch/commit for acceptance if needed**

Cruft updates compare commits. If acceptance requires simulating a later template change, use a temporary local clone or branch under `/tmp`, not the main template worktree, unless the implementation commits are already in place.

- [ ] **Step 3: Try actual cruft creation using uvx**

Run from a clean temporary directory:

```bash
rm -rf /tmp/hs-service-template-cruft-acceptance
mkdir -p /tmp/hs-service-template-cruft-acceptance
cd /tmp/hs-service-template-cruft-acceptance
uvx cruft create /home/clt/PersonalProjects/hs-service-template \
  --no-input \
  --extra-context '{"service_name":"acceptance","repository_name":"acceptance-service","service_group":"Media","service_icon":"app","base_domain":"example.com","default_port":"8080","include_proxy_config":"y"}'
```

Expected: generated repo at `/tmp/hs-service-template-cruft-acceptance/acceptance-service` with `.cruft.json` and `pyproject.toml`.

If this fails because the harness blocks `uvx`, record the exact command and error in the final implementation notes and do not claim end-to-end cruft behavior is verified.

- [ ] **Step 4: Verify generated cruft config**

```bash
cd /tmp/hs-service-template-cruft-acceptance/acceptance-service
python3 - <<'PY'
from pathlib import Path
import tomllib
expected = [
    "docker-compose.yml",
    "stack.env",
    "configurations/locations.ini",
    "configurations/data/**",
    "swag/proxy-confs/**",
]
data = tomllib.loads(Path("pyproject.toml").read_text())
assert data["tool"]["cruft"]["skip"] == expected
PY
```

Expected: exit 0.

- [ ] **Step 5: Verify skipped file behavior with a real cruft update**

This step is required whenever `uvx cruft` can run. Skip it only if the harness blocks `uvx cruft`; if skipped, record the exact command attempted and the error.

Because robust cruft update acceptance requires two template commits, do the simulation in `/tmp` so the real template repo is not polluted:

1. Copy or clone `/home/clt/PersonalProjects/hs-service-template` to `/tmp/hs-service-template-cruft-template`.
2. In the temporary template, ensure the implementation files are committed so cruft has a baseline template commit.
3. Create a downstream repo with `uvx cruft create /tmp/hs-service-template-cruft-template`.
4. Initialize/commit the generated downstream repo if cruft did not create it as a clean git repo:
   ```bash
   cd /tmp/hs-service-template-cruft-acceptance/acceptance-service
   git init
   git add -A
   git commit -m "test: generated baseline"
   ```
5. Customize downstream skipped files:
   - `docker-compose.yml`
   - `configurations/data/example.conf`
   - `swag/proxy-confs/acceptance.subdomain.conf`
6. Commit the downstream customizations:
   ```bash
   git add docker-compose.yml configurations/data/example.conf swag/proxy-confs/acceptance.subdomain.conf
   git commit -m "test: customize skipped files"
   ```
7. In the temporary template, make and commit simulated template changes to those same skipped paths and to a non-skipped path such as `{{cookiecutter.repository_name}}/README.md`.
8. Run `uvx cruft update --skip-apply-ask --refresh-private-variables` in the downstream repo.
9. Verify downstream customized skipped file contents are unchanged.
10. Verify the non-skipped README receives the simulated template update.

Expected: skipped files keep downstream content; non-skipped README updates.

- [ ] **Step 6: Commit no acceptance artifacts**

Confirm no `/tmp` acceptance artifacts are added to git.

---

## Chunk 5: Final verification and handoff to downstream update

### Task 5: Verify implementation and prepare next-step instructions

**Files:**
- No additional source files expected.

- [ ] **Step 1: Run final render tests again**

```bash
COOKIECUTTER_SITE=/home/clt/.local/share/pipx/venvs/cookiecutter/lib/python3.12/site-packages \
COOKIECUTTER_CONFIG=/tmp/cookiecutter_config.yaml \
PYTHONPATH="$COOKIECUTTER_SITE:$PYTHONPATH" \
python3 -m pytest tests/test_template.py -v
```

Expected: all tests pass.

- [ ] **Step 2: Inspect final git status**

```bash
git status --short
```

Expected: no tracked modifications. Unrelated untracked dotfiles may remain and should not be touched.

- [ ] **Step 3: Prepare downstream migration notes for `hs-open-webui`**

Record the next commands for the downstream repo:

```bash
cd /home/clt/PersonalProjects/hs-open-webui
# First add this top-level key to .cruft.json while preserving all existing keys:
# "skip": [
#   "docker-compose.yml",
#   "stack.env",
#   "configurations/locations.ini",
#   "configurations/data/**",
#   "swag/proxy-confs/**"
# ]
uvx cruft update --skip-apply-ask --refresh-private-variables --allow-untracked-files
```

Before committing the downstream update, verify `docker-compose.yml`, `stack.env`, `configurations/locations.ini`, `configurations/data/**`, and `swag/proxy-confs/**` were not changed by cruft.

- [ ] **Step 4: Final implementation summary**

Report:

- commits created,
- tests run with exact command/output summary,
- whether `uvx cruft create/update` acceptance verification ran or was blocked,
- next downstream update step.
