# Homelab Service Template

This repository is a [Cookiecutter](https://github.com/cookiecutter/cookiecutter) template (designed to be used with [cruft](https://cruft.github.io/cruft/)) that bootstraps a homelab service repository with:

1. **Docker Compose** service definition with [Homepage](https://github.com/gethomepage/homepage) discovery labels
2. **CI workflows** that validate the Compose file, deploy to [Portainer](https://docs.portainer.io/start/install-ce), and (optionally) push SWAG nginx configs to the reverse proxy host over SSH
3. **Optional SSH-based config deployment** for versioned service configuration files
4. **Semantic release** automation and **cruft-based template syncing**

The generated project contains everything needed to go from Git push to running container — including validation, deployment, and documentation.

> **Note:** This template assumes an existing homelab infrastructure with Docker Compose, an external reverse proxy (SWAG/nginx), and Portainer. It does not set up SWAG itself — it deploys *config files* to those services remotely via SSH.

---

## Prerequisites

### Where you run cruft (your local machine)

- `git`
- `cruft` (install with `pip install cruft`)
- `sh`, `gitleaks`, `node` + `semantic-release` (only if you plan to run the CI scripts locally)

### On the target server

- Docker Compose v2+
- An external Docker network named `service_internal_lan` (used by the generated Compose file to connect the service to your reverse proxy or other services)

Create the network if it does not exist:

```bash
docker network create service_internal_lan
```

---

## Generate a service repository

Use `cruft create` (not bare `cookiecutter`) so the generated repo can later sync with template improvements:

```bash
cruft create https://github.com/<your-org>/hs-service-template.git
```

You will be prompted for:

| Prompt | Description |
|--------|-------------|
| `repository_name` | Folder/repo name that will be created (e.g. `my-service`) |
| `service_name` | Used for the container name and SWAG config filename |
| `service_group` | Homepage group label (e.g. `Media`, `Automation`) |
| `service_icon` | Homepage icon identifier (e.g. `app`, `docker`) |
| `base_domain` | Base domain served by your reverse proxy (e.g. `example.com`) |
| `default_port` | Internal port exposed by the service container |
| `include_proxy_config` | `y`/`n` — whether to scaffold a SWAG reverse-proxy config and deploy workflow |

After generation you get a ready-to-commit repository under `{{cookiecutter.repository_name}}/`.

### Proxy toggle

- When `include_proxy_config = y` (default) the project includes `swag/proxy-confs/{{ cookiecutter.service_name }}.subdomain.conf`, the `deploy-swag-config.yml` workflow, and the bash script that uploads the config to your remote SWAG host.
- When set to `n`, the post-generation hook removes the `swag/` directory entirely. The workflow and script handle the absence of proxy files by exiting cleanly until you add one later.

---

## Template contents

```
{{cookiecutter.repository_name}}/
├── .github/workflows/
│   ├── cruft-update.yml                  # Weekly cruft-based template sync
│   ├── deploy-stack.yml                  # Compose validation + Portainer deploy
│   ├── deploy-swag-config.yml            # SSH upload of SWAG nginx config
│   ├── deploy-configurations.yml         # SSH upload of service config files
│   └── reusable-portainer-redeploy.yml   # Shared Portainer redeploy logic
├── configurations/
│   ├── data/                             # Service config files (versioned here)
│   │   └── .gitkeep
│   └── locations.ini                     # Maps config files → remote destinations
├── scripts/
│   └── deploy_swag_config.sh             # POSIX script: upload + validate + reload nginx
├── swag/proxy-confs/
│   ├── .gitkeep
│   └── {{cookiecutter.service_name}}.subdomain.conf   # SWAG nginx site config (jinja)
├── docker-compose.yml                    # Service definition (jinja)
├── stack.env                             # Runtime env vars (template)
├── .gitleaks.toml                        # Secrets-scan allowlist
├── .gitignore
├── pyproject.toml                        # Cruft skip configuration only
├── renovate.json.example                 # Renovate dependency dashboard config
├── README.md                             # Per-service documentation (jinja)
└── .github/                              # CI/CD workflows (described above)
```

---

## Generated service files

### `docker-compose.yml` — Service definition

The generated Compose file includes:

- The container with configurable environment variables (`TZ`, `PUID`, `PGID`)
- An external network (`service_internal_lan`) for communication with your reverse proxy
- Persistent volume at `/data/${SERVICE_NAME}`
- **Homepage labels** for automatic service discovery (`homepage.group`, `homepage.icon`, `homepage.href`)

The container image (`your-image:tag`) is a placeholder — replace it with the actual image before first deployment.

### `stack.env` — Runtime variables

Required environment variables used by the generated Compose file and CI workflows:

| Variable | Description |
|----------|-------------|
| `SERVICE_NAME` | Subdomain (and container name) for the service |
| `BASE_DOMAIN` | Base domain (e.g. `example.com`) |
| `TZ` | Container timezone (e.g. `Europe/Rome`) |
| `PUID` | User ID that owns mounted data |
| `PGID` | Group ID that owns mounted data |

### `swag/proxy-confs/` — SWAG nginx config (optional)

When `include_proxy_config = y`, a [SWAG](https://docs.linuxserver.io/general/swag/) subdomain config is scaffolded with `nginx -t` validation before reload. This config is *deployed* to your remote SWAG host via the CI workflow — it is not used locally.

---

## CI/CD workflows

### 1. Docker Compose Validation + Portainer Deploy (`deploy-stack.yml`)

Triggered by pushes to `main` that change `docker-compose.yml`, `stack.env`, or the deploy workflows themselves.

**Steps:**
1. **Validate** — runs `docker compose config --quiet` to verify the YAML
2. **Deploy** — calls `reusable-portainer-redeploy.yml` which:
   - Resolves the stack name from the repository name
   - Creates the stack in Portainer if it does not exist (linked to the Git repo with auto-update enabled)
   - Triggers an immediate redeploy via a Portainer webhook
   - Configures a 5-minute polling interval for automatic updates

#### Required secrets and variables for Portainer deploy

| Name | Type | Purpose |
|------|------|---------|
| `PORTAINER_ACCESS_TOKEN` | secret | Portainer user API token |
| `GIT_USERNAME` | secret | Git username for repository authentication in Portainer |
| `GIT_TOKEN` | secret | Git token for the same user |
| `PORTAINER_URL` | variable | Portainer endpoint URL (without `/api` suffix) |
| `PORTAINER_ENVIRONMENT_ID` | variable | Portainer environment (endpoint) ID |

> **Stack lifecycle:** The stack name is derived from the repository name. Changing the repository name after creation will cause the workflow to attempt creating a *new* stack. If the old stack still exists in Portainer, the new one will coexist — the old one will not be cleaned up automatically.

---

### 2. Deploy SWAG Reverse Proxy Config (`deploy-swag-config.yml`)

Triggered by pushes to `main` that affect `swag/proxy-confs/**`, `scripts/deploy_swag_config.sh`, or the workflow itself. Also supports `workflow_dispatch` with an optional `config_path` input.

**Workflow behavior:**
1. Loads SSH credentials from repository secrets
2. Calls `scripts/deploy_swag_config.sh` which:
   - Auto-detects a single `*.subdomain.conf` or `*.subfolder.conf` in `swag/proxy-confs/` (or uses the explicit path from `config_path`)
   - Uploads the file to the remote host via `scp`
   - Installs it at `SWAG_REMOTE_CONFIG_PATH` preserving the original filename
   - Runs `nginx -t` inside the SWAG container to validate the config
   - On success: removes the backup and reloads nginx
   - On failure: restores the backup and exits with an error
3. If `swag/proxy-confs/` does not exist or is empty, the job exits successfully without deploying

#### Required secrets and variables for SWAG deploy

| Name | Type | Purpose |
|------|------|---------|
| `DEPLOY_SSH_KEY` | secret | Private key for SSH access to the SWAG host |
| `DEPLOY_SSH_HOST` | secret | Hostname/IP of the SWAG machine |
| `DEPLOY_SSH_USER` | secret | SSH user with permissions to manage SWAG |
| `DEPLOY_SSH_PORT` | secret (optional) | Non-default SSH port |
| `SWAG_CONTAINER_NAME` | secret (optional) | Docker container name if different from `swag` |
| `SWAG_REMOTE_CONFIG_PATH` | variable | Directory or absolute file path where proxy configs live on the remote host |
| `DEPLOY_KNOWN_HOSTS` | secret (optional) | `known_hosts` entry so SSH host-key verification succeeds |

#### How to populate `DEPLOY_KNOWN_HOSTS`

Run this command from a machine that can reach the remote host:

```bash
ssh-keyscan -H <hostname> -p <port>
```

Use the output verbatim as the secret value.

---

### 3. Deploy Service Configuration Files (`deploy-configurations.yml`)

This workflow uploads versioned configuration files from `configurations/data/` to a remote host over SSH. Target paths are declared in `configurations/locations.ini`.

**How the process works:**

1. **Assessment** — The workflow checks that `configurations/data/` and `configurations/locations.ini` are consistent:
   - Every file in `data/` must have a mapping entry in `locations.ini`
   - Every entry in `locations.ini` must reference an existing file in `data/`
   - If both are empty/missing, the workflow skips deployment cleanly

2. **Credential resolution** — Determines which set of SSH credentials to use:
   - If `CONFIG_DEPLOY_SSH_HOST` variable is set → uses `CONFIG_DEPLOY_*` credentials (separate machine)
   - If `CONFIG_DEPLOY_SSH_HOST` is not set → falls back to `DEPLOY_SSH_*` credentials (same machine as SWAG)

3. **Deployment** — For each file in `data/`, it:
   - Uploads the file to a temporary location on the remote host via `scp`
   - Installs it at the target path with `install -Dm644`
   - Keeps a `.bak` backup of any pre-existing file

4. **Rollback on failure** — If any upload fails, the `ERR` trap restores all previously deployed files from their `.bak` backups, then removes the backups of successfully restored files.

5. **Redeploy trigger** — If the push also changed `docker-compose.yml` or `stack.env`, the separate deploy-stack workflow already handles the redeploy. Otherwise, the configuration workflow triggers a redeploy via the reusable Portainer workflow, so the service picks up the new configs.

#### Credentials — same machine as SWAG (default)

No extra setup — the workflow reuses the existing `DEPLOY_SSH_KEY`, `DEPLOY_SSH_HOST`, `DEPLOY_SSH_USER`, `DEPLOY_SSH_PORT`, and `DEPLOY_KNOWN_HOSTS` secrets.

#### Credentials — separate config host

| Name | Type | Purpose |
|------|------|---------|
| `CONFIG_DEPLOY_SSH_HOST` | variable | Hostname/IP of the config target |
| `CONFIG_DEPLOY_SSH_USER` | variable | SSH user allowed to manage remote files |
| `CONFIG_DEPLOY_SSH_PORT` | variable (optional) | Non-default SSH port (defaults to 22) |
| `CONFIG_DEPLOY_SSH_KEY` | secret | Private key for SSH access |
| `CONFIG_DEPLOY_KNOWN_HOSTS` | secret (optional) | Server's `known_hosts` entry |

#### `locations.ini` format

```
<file_name>:/absolute/remote/path/<file_name>
```

Example:

```ini
app.conf:/etc/myapp/app.conf
init.sql:/docker-entrypoint-initdb.d/init.sql
```

---

### 4. Template Auto-Update via Cruft (`cruft-update.yml`)

This repository (the template itself) includes a weekly workflow in each generated repo that checks for upstream template changes.

The workflow in generated repos:
- Runs every Monday at 3:00 UTC (and on `workflow_dispatch`)
- Uses `cruft check` to detect changes
- On new template changes, re-renders with the project's saved variables
- Pushes a branch (`cruft/update`) and opens a pull request

> **Note:** The cruft workflow in generated repos is **hardcoded to `gitea.cltec.dev`** as the Gitea instance. If you use GitHub, GitLab, or a different Gitea server, edit the API endpoint URL in `.github/workflows/cruft-update.yml` after generation.

#### Files excluded from cruft updates

These files are customization points and are skipped during `cruft update` (configured in `pyproject.toml`):

| Path | Why it is skipped |
|------|-------------------|
| `docker-compose.yml` | Service image, volumes, environment, labels, and networks often diverge from the template. |
| `stack.env` | Runtime stack values are deployment-specific. |
| `configurations/locations.ini` | Remote file destinations are environment-specific. |
| `configurations/data/**` | Versioned service configuration payloads are downstream-owned. |
| `swag/proxy-confs/**` | Proxy routing, headers, auth, and paths may need service-specific changes. |

`pyproject.toml` exists **only** to hold cruft configuration — it does not make the repository a Python package.

#### Upgrading a repo generated with an older template version

Repos created before this skip policy was introduced lack `pyproject.toml` and therefore have **no skip rules**. Running `cruft update` from such an older baseline will overwrite the customized files listed above — including `docker-compose.yml` and `stack.env` — with template defaults.

To protect an older repo **before the first update** against the new template:

1. Open the repo's `.cruft.json` and add a top-level `"skip"` key while preserving all existing keys:

```json
{
  "template": "...",
  "commit": "...",
  "context": { "cookiecutter": { "...": "..." } },
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

2. Run the update:

```bash
cruft update --skip-apply-ask --refresh-private-variables
```

After this run, the generated `pyproject.toml` appears in the repo and future updates are protected automatically. Leaving the manually added skip list in `.cruft.json` is safe — cruft merges both sources.

> **Sanity check:** After the update completes, verify that `docker-compose.yml`, `stack.env`, `configurations/locations.ini`, `configurations/data/*`, and `swag/proxy-confs/*` still contain your customization and were not replaced by the template.

---

## Local development workflow

1. Generate the repo with cruft: `cruft create https://github.com/<your-org>/hs-service-template.git`
2. Fill `stack.env` from the generated template values
3. Edit `docker-compose.yml` — replace `your-image:tag` with the actual image, adjust volumes/ports/networks as needed
4. Optionally add config files to `configurations/data/` and map them in `configurations/locations.ini`
5. Validate locally:
   ```bash
   cd {{cookiecutter.repository_name}}
   docker compose --env-file stack.env config --quiet
   ```
6. Commit and push to `main`

The CI pipeline will validate the Compose file, create/update the Portainer stack, and (if configured) deploy the SWAG config and service configuration files.

---

## Philosophy

- **Git is the source of truth** — no manual changes on servers. Every deployment artifact is versioned.
- **All configuration is expressed as code** and validated with portable tooling (Docker Compose, `nginx -t`, `gitleaks`).
- **Reverse proxy automation is opt-in** — the proxy toggle lets you decide whether to scaffold SWAG deployment.
- **No secrets committed** — runtime variables live in `stack.env` (populated from CI secrets or a local `.env`).
- **Template auto-updates via cruft** — generated repos stay in sync with template improvements through automated pull requests.

With these conventions, rolling out a new homelab service is as simple as: generate the repo → configure the image → push to main. All supporting automation (validation, deployment, releases) is ready out of the box.
