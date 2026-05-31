# {{ cookiecutter.service_name | title }}

## Overview
Infrastructure-as-code template for deploying the {{ cookiecutter.service_name | title }} service in a homelab environment via Docker Compose and optional SWAG reverse proxy automation.

## Required environment variables
| Variable | Description |
|----------|-------------|
| SERVICE_NAME | Subdomain (and container name) for the service |
| BASE_DOMAIN | Base domain served by Traefik/SWAG |
| TZ | Container timezone |
| PUID | User ID that owns mounted data |
| PGID | Group ID that owns mounted data |

## Public URL
`https://${SERVICE_NAME}.${BASE_DOMAIN}`

## Healthcheck
HTTP endpoint exposed on port {{ cookiecutter.default_port }}.

## Local deployment
1. Copy `.env.example` to `.env` and fill the variables above.
2. Ensure the external Docker network referenced in `docker-compose.yml` exists (e.g. `docker network create proxy`).
3. Run `docker compose up -d` from the repository root to start the service.

## Monitoring
The service can be monitored from Uptime Kuma using the public URL shown above.

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

## Configuration deployment workflow
The `deploy-configurations.yml` workflow uploads versioned configuration files stored in `configurations/data` to the remote host over SSH. Target paths are declared in `configurations/locations.ini`, one per line in the format:
`<file_name>:/absolute/remote/path/<file_name>`

Behavior rules:
- If `configurations/data` and `configurations/locations.ini` are both empty, the workflow skips configuration deployment.
- If a file exists in `configurations/data` without a matching line in `configurations/locations.ini`, the workflow fails.
- If `configurations/locations.ini` references a file not present in `configurations/data`, the workflow fails.
- If any upload fails, previously deployed files are restored from backups.

### Required secrets for configuration deployment

The configuration deployment workflow targets the **same machine as SWAG** by default. Set `CONFIG_DEPLOY_SSH_HOST` (a repository **variable**) to target a **separate machine** instead.

#### Targeting the same machine as SWAG (default)

No additional credentials needed — the workflow reuses:
- `DEPLOY_SSH_KEY`, `DEPLOY_SSH_HOST`, `DEPLOY_SSH_USER` (secrets, already configured for SWAG)
- `DEPLOY_SSH_PORT`, `DEPLOY_KNOWN_HOSTS` (optional secrets)

#### Targeting a separate machine

Configure these additional items:

| Name | Type | Purpose |
|------|------|---------|
| `CONFIG_DEPLOY_SSH_HOST` | variable | Hostname/IP of the config target |
| `CONFIG_DEPLOY_SSH_USER` | variable | SSH user allowed to manage remote files |
| `CONFIG_DEPLOY_SSH_PORT` | variable (optional) | Non-default SSH port (defaults to 22) |
| `CONFIG_DEPLOY_SSH_KEY` | secret | Private key for SSH access |
| `CONFIG_DEPLOY_KNOWN_HOSTS` | secret (optional but recommended) | Server's `known_hosts` entry |

When `CONFIG_DEPLOY_SSH_HOST` is set, the workflow uses `CONFIG_DEPLOY_*` credentials exclusively. When absent, it falls back to `DEPLOY_SSH_*`.

## Reverse proxy deployment workflow
The repository ships with a GitHub/Gitea Action (`.github/workflows/deploy-swag-config.yml`) that uploads SWAG nginx configs via `scripts/deploy_swag_config.sh` whenever a proxy file changes or on manual dispatch. The script preserves the original filename, validates nginx inside the `swag` container, and reloads the proxy only after a successful `nginx -t`.

### Required secrets and variables
Configure these items in the generated repository before running the workflow:
- `DEPLOY_SSH_KEY` (secret): Private key used to connect to the remote SWAG host.
- `DEPLOY_SSH_HOST` (secret): Hostname or IP address of the target server.
- `DEPLOY_SSH_USER` (secret): SSH user allowed to manage SWAG.
- `DEPLOY_SSH_PORT` (secret, optional): Non-default SSH port.
- `SWAG_CONTAINER_NAME` (secret, optional): Docker container name if it is not `swag`.
- `SWAG_REMOTE_CONFIG_PATH` (repository variable preferred, secret fallback): Absolute directory (or file path) on the remote host where proxy configs live.
- `DEPLOY_KNOWN_HOSTS` (secret, optional but recommended): Contents of the server’s `known_hosts` entry to avoid host-key prompts.

The workflow accepts an optional `config_path` input on `workflow_dispatch`. When the input is blank, the deploy script scans `swag/proxy-confs/` for exactly one file that matches `*.subdomain.conf` or `*.subfolder.conf`, fails if more than one is found, and does nothing if none exist.

{% if cookiecutter.include_proxy_config|lower == 'y' %}
### Included proxy file
- Location: `swag/proxy-confs/{{ cookiecutter.service_name }}.subdomain.conf`
- Upstream container: `{{ cookiecutter.service_name }}` listening on port `{{ cookiecutter.default_port }}`.
Keep only one proxy file in this directory; the automation deploys whichever file is present and keeps its original name on the remote SWAG host.
{% else %}
### Adding a proxy later
This project was generated without a SWAG configuration file. To enable the workflow:
1. Create `swag/proxy-confs/` and add exactly one file named `*.subdomain.conf` or `*.subfolder.conf`.
2. Re-run the workflow (or push the file) so the deploy script can detect and upload it.
{% endif %}

### Manual execution
Run the script locally if needed:
```sh
SWAG_REMOTE_CONFIG_PATH=/remote/path scripts/deploy_swag_config.sh
```
Pass an explicit file and remote target path to override auto-detection:
```sh
scripts/deploy_swag_config.sh swag/proxy-confs/<file>.conf /remote/path/
```
