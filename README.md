# Homelab Service Template

This repository is a Cookiecutter template that bootstraps homelab services with Docker Compose, Traefik, Homepage, and optional SWAG reverse-proxy automation. The generated project contains everything needed to deploy from Git, validate with CI, and document required variables.

---

## Prerequisites

Install the following where you run Cookiecutter:

- `git`
- `cookiecutter`
- `docker` (optional, for local runs)
- `sh`, `gitleaks`, `node` + `semantic-release` if you plan to execute the CI scripts locally

On the remote host, ensure Docker Compose v2 and the external `proxy` network exist.

---

## Generate a service repository

```bash
cookiecutter https://github.com/<org>/clt-hs-compose-template.git
```

You will be prompted for:

| Prompt | Description |
|--------|-------------|
| `repository_name` | Folder/repo name that will be created |
| `service_name` | Used for the container name, Traefik router, and SWAG config |
| `service_group` | Homepage group label |
| `service_icon` | Homepage icon |
| `base_domain` | Domain served by Traefik/SWAG |
| `default_port` | Internal port exposed by the service |
| `include_proxy_config` | `y`/`n` to decide whether to scaffold a SWAG config and deploy workflow |

After generation you get a ready-to-commit repository under `{{cookiecutter.repository_name}}/`.

### Proxy toggle
- When `include_proxy_config = y` (default) the project includes `swag/proxy-confs/{{ cookiecutter.service_name }}.subdomain.conf`, the deploy workflow, and the bash script that uploads the config.
- When set to `n`, the post-generation hook removes `swag/`; the workflow and script handle the absence of proxy files by exiting cleanly until you add one.

---

## Template contents

- `docker-compose.yml` – service definition with Traefik and Homepage labels.
- `.env.example` – required runtime variables (`SERVICE_NAME`, `BASE_DOMAIN`, `TZ`, `PUID`, `PGID`).
- `scripts/deploy_swag_config.sh` – uploads a single `*.subdomain.conf` or `*.subfolder.conf` file, preserving its filename on the remote SWAG host.
- `.github/workflows/deploy-swag-config.yml` – runs on pushes to proxy files or manual dispatch and invokes the deploy script.
- `ci/check.sh` – validates structure, env vars, and runs Gitleaks.
- `ci/release.sh` – semantic-release wrapper.

---

## Local validation & release

1. Copy `.env.example` to `.env` and fill the values.
2. Run `docker compose up -d` (optional) to test locally.
3. Execute `./ci/check.sh` before committing to ensure required files and secrets scanning pass.
4. Use Conventional Commits (`feat: ...`, `fix: ...`).
5. Publish releases with `./ci/release.sh` when ready.

---

## Reverse proxy workflow setup

If proxy automation is enabled, configure the following in the generated repository before triggering the workflow:

| Name | Type | Purpose |
|------|------|---------|
| `DEPLOY_SSH_KEY` | secret | Private key for SSH access to the SWAG host |
| `DEPLOY_SSH_HOST` | secret | Hostname/IP of the SWAG machine |
| `DEPLOY_SSH_USER` | secret | SSH user with permissions to manage SWAG |
| `DEPLOY_SSH_PORT` | secret (optional) | Non-default SSH port |
| `SWAG_CONTAINER_NAME` | secret (optional) | Docker container name if different from `swag` |
| `SWAG_REMOTE_CONFIG_PATH` | repository variable preferred (secret fallback) | Directory or absolute file path where proxy configs live on the remote host |
| `DEPLOY_KNOWN_HOSTS` | secret (optional but recommended) | `known_hosts` entry so SSH host-key verification succeeds |

Workflow behavior:
- Triggered by pushes affecting `swag/proxy-confs/**`, the deploy script, or the workflow itself, and via `workflow_dispatch`.
- Optional `config_path` input lets you force a specific file. When omitted, the script scans `swag/proxy-confs/` and requires exactly one `*.subdomain.conf` or `*.subfolder.conf` file. If the directory is absent or empty the job exits successfully without deploying.
- On deploy, the script copies the config to a temporary location, installs it at `SWAG_REMOTE_CONFIG_PATH`, validates `nginx -t` inside the SWAG container, and reloads nginx.

---

## Philosophy

- Git is the source of truth; no manual changes on servers.
- All configuration is expressed as code and validated with portable tooling.
- Reverse proxy automation is opt-in and safe by default.
- No secrets committed—environment variables live in `.env` or CI secrets.

With these conventions, rolling out a new homelab service is as simple as generating the repo, configuring the stack, and pushing to main. All supporting automation (validation, deployment, releases) is ready out of the box.
