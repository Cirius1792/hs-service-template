# Spec: Optional SSH Credentials for Configuration Deployment

**Status:** Draft → Review  
**Date:** 2026-05-30  
**Scope:** `{{cookiecutter.repository_name}}/.github/workflows/deploy-configurations.yml` + docs

---

## 1. Problem Statement

Currently `deploy-configurations.yml` **always** requires three repository variables and two secrets under the `CONFIG_DEPLOY_SSH_*` namespace:

| Current credential | GHA type |
|---|---|
| `CONFIG_DEPLOY_SSH_HOST` | `vars` |
| `CONFIG_DEPLOY_SSH_USER` | `vars` |
| `CONFIG_DEPLOY_SSH_PORT` | `vars` |
| `CONFIG_DEPLOY_SSH_KEY` | `secrets` |
| `CONFIG_DEPLOY_KNOWN_HOSTS` | `secrets` |

When the configuration target machine is the **same** machine as the SWAG reverse proxy, these duplicate the `DEPLOY_SSH_*` credentials already configured for `deploy-swag-config.yml`. Users must maintain two identical sets of SSH credentials, creating unnecessary friction and a vector for drift.

## 2. Goal

Make `CONFIG_DEPLOY_SSH_*` **optional**. When absent, `deploy-configurations.yml` falls back to `DEPLOY_SSH_*` credentials (the same ones used by `deploy-swag-config.yml`).

**Desired UX (`vars` and `secrets` needed in the generated repo):**

| Scenario | Host sentinel | SSH key needed | SSH host needed |
|----------|---------------|----------------|-----------------|
| Config on same machine as SWAG | `CONFIG_DEPLOY_SSH_HOST` **not set** | `DEPLOY_SSH_KEY` (already required for proxy deploy) | `DEPLOY_SSH_HOST` (already required for proxy deploy) |
| Config on different machine | `CONFIG_DEPLOY_SSH_HOST` **set** | `CONFIG_DEPLOY_SSH_KEY` | `CONFIG_DEPLOY_SSH_HOST` / `CONFIG_DEPLOY_SSH_USER` / `CONFIG_DEPLOY_SSH_PORT` |

## 3. Design Constraints

| # | Constraint | Implication |
|---|-----------|-------------|
| C1 | `DEPLOY_SSH_HOST` is a **secret**; `CONFIG_DEPLOY_SSH_HOST` is a **var** | Cannot compare secrets in `if:` conditions. The probe must use the **var** (`vars.CONFIG_DEPLOY_SSH_HOST`) as the sentinel. |
| C2 | `webfactory/ssh-agent` input is a literal `${{ secrets.* }}` expression, not an env var | Cannot make the key dynamic inside a single action invocation. Two parallel steps are required. |
| C3 | `secrets.*` context is unavailable in `if:` | The fallback check must rely on the `vars` sentinel, not on whether `secrets.DEPLOY_SSH_KEY` is set. |
| C4 | `DEPLOY_KNOWN_HOSTS` is optional in both namespaces | The known_hosts step must work whether or not the secret exists in the active namespace. |
| C5 | `redeploy-stack` job is independent of SSH credentials | No changes needed. |
| C6 | Template uses Cookiecutter Jinja; GHA `${{ }}` expressions must be escaped as `{{ '${{ }}' }}` | Inside `{% raw %}...{% endraw %}` blocks, GHA expressions pass through unmolested. Outside raw blocks, every `${{ }}` needs the Cookiecutter escape. |
| C7 | Both namespace secrets may be resolved into `env:` simultaneously | Harmless (same runner), but worth documenting as intentional so future readers don't "clean it up." |

## 4. Proposed Solution: Sentinel-Based Branching

**Sentinel:** `vars.CONFIG_DEPLOY_SSH_HOST` — if empty, route to `DEPLOY_SSH_*`. Otherwise route to `CONFIG_DEPLOY_SSH_*`.

**Flow:**

```
vars.CONFIG_DEPLOY_SSH_HOST set?
 ├── YES → namespace=config → known_hosts(CONFIG_DEPLOY) → ssh-agent(CONFIG_DEPLOY) → deploy(CONFIG_DEPLOY)
 └── NO  → namespace=swag   → known_hosts(DEPLOY)         → ssh-agent(DEPLOY)         → deploy(DEPLOY)
```

Three GHA constructs need the credential namespace:

| Construct | Type | Branching strategy |
|-----------|------|--------------------|
| `known_hosts` setup | `run:` step | Single step; both secrets in `env:`, script picks at runtime |
| `Start ssh-agent` | `webfactory/ssh-agent` action | Two parallel steps, each guarded by `if: namespace == ...` |
| Deploy credentials | `run:` step | Single step; both credential sets in `env:`, script picks at runtime |

### 4.1 Probe Step (NEW)

Inserted after the `redeploy_plan` step. Single-purpose: detect which namespace is active.

```yaml
- name: Determine credential namespace
  id: credential_probe
  run: |
    if [ -n "${{ vars.CONFIG_DEPLOY_SSH_HOST }}" ]; then
      echo "namespace=config" >> "$GITHUB_OUTPUT"
    else
      echo "namespace=swag" >> "$GITHUB_OUTPUT"
    fi
```

**Note:** The probe intentionally does NOT output the resolved host/user/port. Outputs from a probe step would redundantly duplicate what's in `env:` on the deploy step. The `namespace` output alone is the single branching point for all subsequent logic.

### 4.2 known_hosts Setup (REPLACES existing `Check known_hosts` + `Configure known_hosts`)

Merge the two-step check+configure pair into a single step that reads from the resolved namespace:

```yaml
- name: Configure known_hosts
  if: steps.config_plan.outputs.should_deploy == 'true'
  env:
    CONFIG_DEPLOY_KNOWN_HOSTS: ${{ secrets.CONFIG_DEPLOY_KNOWN_HOSTS }}
    DEPLOY_KNOWN_HOSTS: ${{ secrets.DEPLOY_KNOWN_HOSTS }}
  run: |
    set -euo pipefail
    if [ "${{ steps.credential_probe.outputs.namespace }}" = "config" ]; then
      SSH_KNOWN_HOSTS="${CONFIG_DEPLOY_KNOWN_HOSTS:-}"
    else
      SSH_KNOWN_HOSTS="${DEPLOY_KNOWN_HOSTS:-}"
    fi
    if [ -n "$SSH_KNOWN_HOSTS" ]; then
      mkdir -p ~/.ssh
      printf '%s\n' "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts
      chmod 600 ~/.ssh/known_hosts
      echo "known_hosts configured for namespace=${{ steps.credential_probe.outputs.namespace }}."
    else
      echo "No known_hosts secret in namespace=${{ steps.credential_probe.outputs.namespace }}; host-key verification may prompt."
    fi
```

**Rationale for merging:** Both `CONFIG_DEPLOY_KNOWN_HOSTS` and `DEPLOY_KNOWN_HOSTS` are optional secrets. Keeping separate check+configure steps per namespace would create 4 steps. Collapsing into one runtime-branching step is simpler to maintain.

**Change from current:** The `Check known_hosts` step is removed. The `Configure known_hosts` step now handles both namespaces inline and degrades gracefully when the optional known_hosts secret is missing from the active namespace.

### 4.3 ssh-agent (REPLACES single `Start ssh-agent` step)

Replace with two steps, each guarded by the namespace output:

```yaml
- name: Start ssh-agent (separate config host)
  if: steps.credential_probe.outputs.namespace == 'config' && steps.config_plan.outputs.should_deploy == 'true'
  uses: webfactory/ssh-agent@v0.9.0
  with:
    ssh-private-key: ${{ secrets.CONFIG_DEPLOY_SSH_KEY }}

- name: Start ssh-agent (same host as SWAG)
  if: steps.credential_probe.outputs.namespace == 'swag' && steps.config_plan.outputs.should_deploy == 'true'
  uses: webfactory/ssh-agent@v0.9.0
  with:
    ssh-private-key: ${{ secrets.DEPLOY_SSH_KEY }}
```

**Rationale:** `webfactory/ssh-agent` takes `ssh-private-key:` as a direct workflow expression (`${{ secrets.* }}`). There is no way to route this dynamically inside a single action invocation — the expression is evaluated at workflow parse time, not step runtime. Two parallel steps with exclusive `if:` conditions are the standard GHA pattern for this.

If the required key secret is missing for the active namespace, GHA will fail the step during expression evaluation with a clear error message (e.g. `The secret 'DEPLOY_SSH_KEY' is not set`).

### 4.4 Deploy Configuration Files Step (REWORKED)

The deploy step's `env:` block provides **both** credential namespaces. The script selects the right one at runtime using the probe output.

```yaml
- name: Deploy configuration files
  if: steps.config_plan.outputs.should_deploy == 'true'
  env:
    # Config namespace (vars)
    CONFIG_DEPLOY_SSH_HOST: ${{ vars.CONFIG_DEPLOY_SSH_HOST }}
    CONFIG_DEPLOY_SSH_USER: ${{ vars.CONFIG_DEPLOY_SSH_USER }}
    CONFIG_DEPLOY_SSH_PORT: ${{ vars.CONFIG_DEPLOY_SSH_PORT }}
    # SWAG namespace (secrets — fallback)
    DEPLOY_SSH_HOST: ${{ secrets.DEPLOY_SSH_HOST }}
    DEPLOY_SSH_USER: ${{ secrets.DEPLOY_SSH_USER }}
    DEPLOY_SSH_PORT: ${{ secrets.DEPLOY_SSH_PORT }}
    # Runtime selector
    CREDENTIAL_NAMESPACE: ${{ steps.credential_probe.outputs.namespace }}
  run: |
    {% raw %}
    set -euo pipefail

    # ── Resolve SSH credentials from the active namespace ──
    if [ "$CREDENTIAL_NAMESPACE" = "config" ]; then
      : "${CONFIG_DEPLOY_SSH_HOST:?Set CONFIG_DEPLOY_SSH_HOST}"
      : "${CONFIG_DEPLOY_SSH_USER:?Set CONFIG_DEPLOY_SSH_USER}"
      DEPLOY_SSH_HOST="$CONFIG_DEPLOY_SSH_HOST"
      DEPLOY_SSH_USER="$CONFIG_DEPLOY_SSH_USER"
      DEPLOY_SSH_PORT="${CONFIG_DEPLOY_SSH_PORT:-22}"
    else
      : "${DEPLOY_SSH_HOST:?Set DEPLOY_SSH_HOST (same host as SWAG)}"
      : "${DEPLOY_SSH_USER:?Set DEPLOY_SSH_USER}"
      DEPLOY_SSH_PORT="${DEPLOY_SSH_PORT:-22}"
    fi

    # ── Rest of existing deploy script (unchanged from here) ──

    MAP_FILE="${{ steps.config_plan.outputs.map_file }}"
    # ...
    {% endraw %}
```

**Key design choice:** Both `secrets.DEPLOY_SSH_*` and `vars.CONFIG_DEPLOY_SSH_*` are resolved into `env:` simultaneously, even in the "separate config host" scenario where the SWAG secrets are unused. This is intentional — GHA resolves all `env:` expressions before the step starts, and there is no security or performance concern (same runner, same trust domain). The alternative (two separate deploy steps with `if:` guards) would duplicate ~80 lines of deployment logic and is worse.

**Port default for both namespaces:** `22` when the port var/secret is empty. Both `DEPLOY_SSH_PORT` and `CONFIG_DEPLOY_SSH_PORT` are optional in their respective namespaces.

## 5. Complete Step-by-Step Pseudocode

Below is the revised `deploy-configs` job structure. Steps marked **(NEW)** or **(MODIFIED)** differ from the current file. Steps marked (no change) are untouched.

```
job: deploy-configs

  step: Checkout repository                        (no change)
  
  step: Assess configuration deployment            (no change)
    → outputs: should_deploy, map_file
  
  step: Assess redeploy responsibility             (no change)
    → output: should_trigger_redeploy
  
  step: Determine credential namespace             (NEW)
    → output: namespace ∈ {config, swag}
       config if vars.CONFIG_DEPLOY_SSH_HOST is non-empty
       swag  otherwise
  
  step: Configure known_hosts                      (MODIFIED — replaces two steps)
    guard: should_deploy == 'true'
    env: CONFIG_DEPLOY_KNOWN_HOSTS + DEPLOY_KNOWN_HOSTS
    script: picks correct secret based on namespace output
  
  step: Start ssh-agent (separate config host)     (NEW — replaces single step)
    guard: namespace == 'config' && should_deploy == 'true'
    key: secrets.CONFIG_DEPLOY_SSH_KEY
  
  step: Start ssh-agent (same host as SWAG)        (NEW — replaces single step)
    guard: namespace == 'swag' && should_deploy == 'true'
    key: secrets.DEPLOY_SSH_KEY
  
  step: Deploy configuration files                 (MODIFIED — env block + credential resolution)
    guard: should_deploy == 'true'
    env: both credential sets + CREDENTIAL_NAMESPACE
    script: resolves DEPLOY_SSH_HOST/USER/PORT at top, then existing deploy logic

job: redeploy-stack                                (no change)
  needs: deploy-configs
  guard: should_trigger_redeploy == 'true'
  uses: reusable-portainer-redeploy.yml
```

## 6. File Changes Summary

| File | Change | What |
|------|--------|------|
| `{{cookiecutter.repository_name}}/.github/workflows/deploy-configurations.yml` | **Modify** | 1 added step (probe), 1 merged step (known_hosts), 1→2 steps (ssh-agent), 1 reworked step (deploy env+script). Net: +1 step count vs. current. |
| `{{cookiecutter.repository_name}}/README.md` | **Modify** | Update "Configuration deployment workflow" section to document optional behavior. |
| `README.md` (root) | **Modify** | Update the "Deploy Reverse Proxy Configuration" table to reference the fallback. |
| `{{cookiecutter.repository_name}}/.github/workflows/deploy-swag-config.yml` | **No change** | Unaffected. |
| `{{cookiecutter.repository_name}}/.github/workflows/deploy-stack.yml` | **No change** | Unaffected. |
| `{{cookiecutter.repository_name}}/.github/workflows/reusable-portainer-redeploy.yml` | **No change** | Unaffected. |
| `cookiecutter.json` | **No change** | No new template fields needed; behavior is purely runtime. |

## 7. README Documentation Changes

### 7.1 Generated README (`{{cookiecutter.repository_name}}/README.md`)

Replace the "Required secrets for configuration deployment" section with:

```markdown
### Required secrets for configuration deployment

The configuration deployment workflow can target either the **same machine** as SWAG (default) or a **separate machine**. The sentinel is `CONFIG_DEPLOY_SSH_HOST`.

#### Targeting the same machine as SWAG (default)

No additional secrets needed — the workflow reuses `DEPLOY_SSH_KEY`, `DEPLOY_SSH_HOST`, `DEPLOY_SSH_USER`, `DEPLOY_SSH_PORT`, and `DEPLOY_KNOWN_HOSTS`.

#### Targeting a separate machine

Configure these items in addition to the SWAG deploy secrets:

- `CONFIG_DEPLOY_SSH_HOST` (variable): Hostname or IP of the config target.
- `CONFIG_DEPLOY_SSH_USER` (variable): SSH user allowed to manage remote files.
- `CONFIG_DEPLOY_SSH_PORT` (variable, optional): Non-default SSH port (defaults to 22).
- `CONFIG_DEPLOY_SSH_KEY` (secret): Private key for SSH access.
- `CONFIG_DEPLOY_KNOWN_HOSTS` (secret, optional but recommended): Server's `known_hosts` entry.

When `CONFIG_DEPLOY_SSH_HOST` is set, the workflow uses the `CONFIG_DEPLOY_*` credentials exclusively. When absent, it falls back to `DEPLOY_SSH_*`.
```

### 7.2 Root README

Update the "Deploy Reverse Proxy Configuration" table to include a note:

```
| CONFIG_DEPLOY_SSH_HOST | variable (optional) | Set to deploy configuration files to a separate host; omit to reuse DEPLOY_SSH_* |
```

The full table can stay as-is; just add the one clarifying row.

## 8. Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| `CONFIG_DEPLOY_SSH_HOST` is set but `CONFIG_DEPLOY_SSH_KEY` is missing | `ssh-agent` step for config namespace fails at expression evaluation with `The secret 'CONFIG_DEPLOY_SSH_KEY' is not set` |
| `CONFIG_DEPLOY_SSH_HOST` is not set and `DEPLOY_SSH_KEY` is missing | `ssh-agent` step for SWAG namespace fails similarly |
| `CONFIG_DEPLOY_SSH_HOST` is an empty string | `[ -n "" ]` → false → `namespace=swag` (correctly falls back) |
| Both namespaces fully configured | Config namespace wins (explicit > implicit); SWAG namespace secrets are resolved into `env:` but unused |
| Known_hosts missing in the active namespace | Step degrades gracefully with a warning; SSH host-key behavior depends on remote's `StrictHostKeyChecking` |
| Known_hosts missing in the **inactive** namespace | Irrelevant — the secret is resolved into `env:` but never read |
| `CONFIG_DEPLOY_SSH_PORT` not set, config namespace active | Defaults to `22` in script (same behavior as SWAG namespace) |
| Workflow triggered by `workflow_dispatch` | No impact — `should_deploy` guard still applies normally |

## 9. Cookiecutter Templating Notes

This is critical for implementation — getting the escaping wrong will produce broken YAML after rendering.

### GHA expressions that must be escaped

Any `${{ }}` that appears **outside** a `{% raw %}...{% endraw %}` block must be escaped as `{{ '${{ }}' }}` so Cookiecutter leaves it intact rather than interpreting it as an undefined Jinja variable.

### Concrete escaping map for each block

| Block | Escaping required? | Notes |
|-------|--------------------|-------|
| Probe step `run:` | No — content is plain shell, no GHA expressions | `if [ -n "${{ vars.CONFIG_DEPLOY_SSH_HOST }}" ]` — actually wait, this **is** a GHA expression inside the `run:` command. It needs escaping since it's not inside `{% raw %}`. Use: `{{ '${{ vars.CONFIG_DEPLOY_SSH_HOST }}' }}` |
| Known_hosts `env:` | Yes — `${{ secrets.* }}` must be escaped | `CONFIG_DEPLOY_KNOWN_HOSTS: {{ '${{ secrets.CONFIG_DEPLOY_KNOWN_HOSTS }}' }}` |
| Known_hosts `run:` | Conditional — the `steps.credential_probe.outputs.namespace` reference in `if`/`echo` is a GHA expression inside raw shell | Always inside double-quoted shell string → treat as GHA expression, escape it |
| ssh-agent `if:` | Yes | `{{ '${{ steps.credential_probe.outputs.namespace == ... }}' }}` |
| ssh-agent `with.ssh-private-key:` | Yes | `{{ '${{ secrets.DEPLOY_SSH_KEY }}' }}` |
| Deploy step `env:` | Yes — all `${{ }}` must be escaped | Same pattern as known_hosts |
| Deploy step `run:` | No — the entire script is inside `{% raw %}...{% endraw %}` | The `${{ steps.config_plan.outputs.map_file }}` reference already follows this pattern in the current file |

**Rule of thumb:** Look at the existing file. Every `${{ }}` in the current `deploy-configurations.yml` is either inside `{% raw %}...{% endraw %}` (so it passes through) or wrapped as `{{ '${{ }}' }}`. Follow the same pattern.

### The probe step escaping (slightly subtle)

The probe step's `if [ -n "${{ vars.CONFIG_DEPLOY_SSH_HOST }}" ]` is NOT inside a `{% raw %}` block. So it must be written as:

```yaml
if [ -n "{{ '${{ vars.CONFIG_DEPLOY_SSH_HOST }}' }}" ]; then
```

This escapes correctly: Cookiecutter sees `{{ '${{ vars... }}' }}`, evaluates it as a literal string `${{ vars.CONFIG_DEPLOY_SSH_HOST }}`, and passes it through to the rendered YAML.

## 10. Out of Scope

- `deploy-swag-config.yml` — unchanged
- `deploy-stack.yml`, `reusable-portainer-redeploy.yml` — unchanged
- Service-specific files (`docker-compose.yml`, `configurations/*`, `stack.env`) — unchanged
- Adding a dedicated boolean toggle (`CONFIG_DEPLOY_ON_SEPARATE_HOST`) — the host var itself serves as the sentinel; adding a boolean would be a second concept for the same decision

## 11. Verification Checklist

- [ ] Template renders correctly with `include_proxy_config=y` — all workflows materialize without unresolved cookiecutter vars
- [ ] Template renders correctly with `include_proxy_config=n` — same
- [ ] Rendered `deploy-configurations.yml` has the probe step, merged known_hosts, two ssh-agent steps, reworked deploy step
- [ ] Rendered `deploy-swag-config.yml` is byte-identical to current (no regressions)
- [ ] Rendered `deploy-stack.yml` is identical to current
- [ ] `./ci/check.sh` passes in the rendered output
- [ ] `gitleaks detect --source . --no-git` passes
- [ ] (Manual) Push to a test service repo with `CONFIG_DEPLOY_SSH_HOST` set → config namespace used
- [ ] (Manual) Push to a test service repo without `CONFIG_DEPLOY_SSH_HOST` → SWAG namespace used
