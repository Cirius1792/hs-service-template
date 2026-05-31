# Cruft Skip Customized Files — Design Spec

**Date:** 2026-05-31
**Status:** Approved

## Goal

Every downstream repo created from `hs-service-template` should be generated with persistent cruft skip rules for files that are expected to diverge after project creation. Future `cruft update` runs must update template-owned boilerplate while leaving service-specific deployment and configuration files untouched.

## Context

- This spec is written against the current `hs-service-template` after the already-merged template work that introduced Portainer deployment, configuration deployment, SWAG proxy support, and cruft auto-update support.
- The current generated template includes the files/directories covered by the skip list: `docker-compose.yml`, `stack.env`, `configurations/locations.ini`, `configurations/data/.gitkeep`, and `swag/proxy-confs/`.
- The current template test suite includes `tests/test_template.py`; this work extends that suite rather than introducing a new test framework.
- Downstream repos are created with `cruft create`, not plain `cookiecutter`.
- Creation command convention is:

  ```bash
  uvx cruft create ssh://git@cltec.dev:222/clt/hs-service-template.git
  ```

- Update command convention is:

  ```bash
  uvx cruft update --skip-apply-ask --refresh-private-variables
  ```

- Cruft writes `.cruft.json` after Cookiecutter generation finishes.
- Cruft officially supports persistent skip rules in either:
  - `.cruft.json` via a top-level `skip` list, or
  - `pyproject.toml` via `[tool.cruft] skip = [...]`.
- Cruft documentation and the cruft 2.16 source show update rendering reads skip paths from `.cruft.json` and extends them with `[tool.cruft].skip` from `pyproject.toml` before computing the template diff.
- A Cookiecutter `post_gen_project` hook is not a reliable way to modify `.cruft.json`, because `.cruft.json` does not exist yet when Cookiecutter hooks run.
- Requiring users to remember `cruft create --skip ...` is fragile and would make correct project creation dependent on tribal knowledge.

## Decision

Generate a `pyproject.toml` in every downstream repo with a `[tool.cruft]` skip list.

This is Option C from the design discussion: template-owned cruft configuration rendered directly into the generated project. It makes the desired behavior automatic immediately after project creation and requires no wrapper script, no manual `--skip` flags, and no post-generation mutation of `.cruft.json`.

## Architecture

The template will render this file into each generated repository:

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

During `cruft update`, cruft reads the downstream repo's `.cruft.json` and also reads `pyproject.toml` if present. It combines the configured skip paths, removes those paths from the old/new rendered template comparison, and therefore does not apply template diffs to those files.

```text
Generated repo
  ├─ .cruft.json              # cruft-owned template state
  ├─ pyproject.toml           # template-generated persistent skip policy
  ├─ docker-compose.yml       # downstream-owned after creation
  ├─ stack.env                # downstream-owned after creation
  ├─ configurations/
  │  ├─ locations.ini         # downstream-owned after creation
  │  └─ data/**               # downstream-owned after creation
  └─ swag/proxy-confs/**      # downstream-owned after creation
```

All skipped paths exist in the current generated template baseline. The glob entries target directories that may initially contain only `.gitkeep` files. Keeping the directory globs in the skip list is intentional: as soon as downstream repos add real files under those directories, cruft should treat those files as downstream-owned.

## Files

| File | Action | Purpose |
|---|---|---|
| `{{cookiecutter.repository_name}}/pyproject.toml` | Create | Persist cruft skip rules in every generated repo |
| `{{cookiecutter.repository_name}}/README.md` | Modify | Document which files are intentionally excluded from template updates |
| `tests/test_template.py` | Modify | Assert the generated repo contains the cruft skip policy |
| Existing downstream `.cruft.json` files | Manual migration | Add the same `skip` list before their next update, if they do not yet have generated `pyproject.toml` |

## Skip policy

### Skipped files

| Path | Reason |
|---|---|
| `docker-compose.yml` | The service image, volumes, environment, labels, and networks are expected to become service-specific after creation. |
| `stack.env` | Generated and committed by the template as Portainer stack environment input, then owned by the downstream service repo after creation. |
| `configurations/locations.ini` | Generated and committed by the template as an example/empty mapping file; downstream repos fill it with environment-specific remote host paths. |
| `configurations/data/**` | The template provides the directory structure; actual config payload files are downstream-owned. |
| `swag/proxy-confs/**` | The template may generate an initial proxy config, but downstream repos may need service-specific routing, headers, auth, or path changes. |

### Not skipped

Template-owned automation and documentation should continue to receive updates:

- `.github/workflows/**`
- `scripts/**`
- `README.md`
- `.gitignore`
- `renovate.json` or future template-managed automation/configuration files
- `.env.example`, if the template adds one later; it should remain documentation/sample configuration, not runtime configuration

This keeps the boilerplate update mechanism valuable while protecting the files most likely to have legitimate downstream drift.

## `pyproject.toml` ownership policy

`pyproject.toml` itself is template-owned because it carries the cruft skip policy. It must not be added to the skip list.

Adding `pyproject.toml` does **not** make generated repos Python packages. The file will not declare a build backend, package metadata, runtime dependencies, or dependency-management tool. It exists only as a standard location for cruft configuration.

Downstream repos may extend `pyproject.toml` with additional tool sections if needed. If a future template update also modifies `pyproject.toml`, any conflict should be resolved manually, preserving `[tool.cruft].skip`. The template should keep `pyproject.toml` minimal to reduce the chance of conflicts.

## Glob semantics

Cruft treats skip entries containing `*` as glob patterns relative to the generated project root. Entries without `*` are treated as paths relative to the generated project root.

The implementation must verify that these patterns match the intended files/directories:

- `configurations/data/**`
- `swag/proxy-confs/**`

If acceptance testing shows that cruft does not skip nested files with `/**` as expected, use a documented-safe equivalent before implementation is accepted.

## Existing downstream migration

For repos that already exist, such as `hs-open-webui`, adding `pyproject.toml` to the template is not enough to protect the first update because the repo does not have that file yet. Before running the next `cruft update`, manually add a top-level `skip` key to the existing `.cruft.json` while preserving all existing keys.

Abbreviated example:

```json
{
  "template": "ssh://git@cltec.dev:222/clt/hs-service-template.git",
  "commit": "...",
  "checkout": null,
  "context": {
    "cookiecutter": {
      "service_name": "open-webui"
    }
  },
  "directory": null,
  "skip": [
    "docker-compose.yml",
    "stack.env",
    "configurations/locations.ini",
    "configurations/data/**",
    "swag/proxy-confs/**"
  ]
}
```

Then run the update with uvx:

```bash
uvx cruft update --skip-apply-ask --refresh-private-variables --allow-untracked-files
```

`--allow-untracked-files` is needed in workspaces that contain unrelated untracked files. If the working tree has tracked modifications, those must still be committed, reverted, or moved aside before cruft can update.

After the update, the generated `pyproject.toml` should be present and future updates can rely on it.

Recommended final state for existing downstream repos: leave the manually added `.cruft.json` `skip` list in place unless there is a specific reason to remove it. Keeping the same skip list in both `.cruft.json` and `pyproject.toml` is redundant but safe because cruft combines the lists. Leaving it avoids a follow-up migration edit and protects the repo if `pyproject.toml` is accidentally removed later.

## Documentation requirements

The generated README should explain:

1. Some files are customization points and intentionally excluded from template updates.
2. The skip list lives in `pyproject.toml` under `[tool.cruft]` for newly generated repos.
3. Existing repos may also carry the same skip list in `.cruft.json` during migration.
4. If the upstream template later improves a skipped file, maintainers must review and port the change manually.
5. New template-owned automation will still flow through `cruft update`.
6. `pyproject.toml` is present only for cruft configuration; it does not mean the generated repo is a Python package or uses Python for runtime/dependency management.
7. When the template changes a skipped file, downstream maintainers must manually diff against the template and port only the relevant changes.

## Testing

The template already has `tests/test_template.py`; extend it rather than creating a new test harness.

Add render-level assertions that verify:

- `pyproject.toml` exists in the generated repo.
- It contains a `[tool.cruft]` section.
- Its `skip` list includes:
  - `docker-compose.yml`
  - `stack.env`
  - `configurations/locations.ini`
  - `configurations/data/**`
  - `swag/proxy-confs/**`
- Generated README mentions the intentionally skipped customization files.

Use `tomllib` when available to parse `pyproject.toml`; otherwise use focused string assertions.

## Acceptance verification

Beyond unit/render tests, verify the behavior with an actual cruft-managed fixture or temporary repo before considering implementation complete:

1. Create a temporary downstream repo with the local template using `uvx cruft create`.
2. Confirm the generated repo contains `pyproject.toml` with `[tool.cruft].skip`.
3. Modify a skipped file in the downstream repo, for example `docker-compose.yml`.
4. Make or simulate a template change that would otherwise alter that skipped file.
5. Run `uvx cruft update --skip-apply-ask --refresh-private-variables` in the downstream repo.
6. Confirm the downstream's customized skipped file remains unchanged.
7. Create or modify a nested file under `configurations/data/`, make or simulate a template change that would otherwise touch the same path, and confirm cruft leaves the downstream file unchanged.
8. Create or modify a nested file under `swag/proxy-confs/`, make or simulate a template change that would otherwise touch the same path, and confirm cruft leaves the downstream file unchanged.
9. Also make or simulate a template change to a non-skipped template-owned file, such as `README.md`, and confirm that the downstream receives that update.

If local `uvx cruft ...` execution is blocked by the harness, document the exact command attempted, the error, and complete the render-level tests. Do not claim end-to-end cruft skip behavior is verified unless this acceptance flow actually runs.

## Error handling and edge cases

| Scenario | Expected behavior |
|---|---|
| User customizes a skipped file | Future cruft updates leave it untouched. |
| Template changes a skipped file later | Downstream does not receive the change automatically; README documents manual review. |
| Downstream removes `pyproject.toml` | Cruft no longer sees generated skip rules; updates may touch customization files unless `.cruft.json` has a skip list. |
| Existing downstream lacks `pyproject.toml` | Manually add skip list to `.cruft.json` before first update. |
| A skipped path does not exist | Cruft skip glob/path is harmless. |
| Downstream adds unrelated sections to `pyproject.toml` | Future template changes may require manual conflict resolution; preserve `[tool.cruft].skip`. |

## Out of scope

- Building a wrapper around `cruft create`.
- Adding Cookiecutter hooks to mutate `.cruft.json`.
- Automatically merging upstream changes into skipped files.
- Changing the service-specific contents of `docker-compose.yml`, `stack.env`, `locations.ini`, or proxy configs as part of this work.

## Manual update procedure for skipped files

When the template changes a skipped file, downstream maintainers who want to consider that change should:

1. Inspect the corresponding file in the template at the new template commit.
2. Compare it with the downstream customized file.
3. Identify whether the change is a generic improvement, security fix, or only a template default/example change.
4. Manually port only the relevant lines into the downstream file.
5. Let the normal downstream deployment/validation workflow verify the customized result.

The generated README must point maintainers to this manual review expectation, especially for security-sensitive files such as proxy configs and deployment definitions.
