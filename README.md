# Homelab Service Template

This repository is a Cookiecutter template that bootstraps homelab services with:
1. Automatic deploy/redeploy in Docker using [Portainer](https://docs.portainer.io/start/install-ce)
2. [SWAG](https://docs.linuxserver.io/general/swag/) reverse proxy setup
3. [Homepage](https://github.com/gethomepage/homepage) link creation

The generated project contains everything needed to deploy from Git, validate with CI, and document required variables.

---

## Prerequisites

Install the following where you run Cookiecutter:

- `git`
- `cookiecutter`
- `sh`, `gitleaks`, `node` + `semantic-release` if you plan to execute the CI scripts locally

On the remote host, ensure Docker Compose v2 and the external `servie_lan` network exist.

The external lan is ment to make the to be deployed service communicate with other services or with the reverse proxy in order to be exposed.

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
- `stack.env` – required runtime variables (`SERVICE_NAME`, `BASE_DOMAIN`, `TZ`, `PUID`, `PGID`).
- `.github` - contains the ci workflows

---

# CI 
## Docker Compose Validation

The docker compose is validated resolving the environment variables as specified in the `stack.env` file. 

If you plan to define your variables outside the repository, you may want to disable this step.

## Deploy/Update Portainer Stack

The repository will contain the required workflows to automatically handle in Portainer: 
- New stack creation, linked to the repository with automatic updates enabled
- Automatic redeploy using webhooks

The stack will have the same name of the repository, which will be used also to retrieve the webhook id, therefore, changing the repository name will cause a new stack to be created (this operation could potentially fail if the old stack have not been destroyed).

In order to make the deploy to work, you need to configure your gitea/github environment with the secrets and variables described below. 

| Name | Type | Purpose |
|------|------|---------|
| `PORTAINER_ACCESS_TOKEN` | secret | Access token generated for your portainer user |
| `GIT_USERNAME` | secret |  Git username to configure in Portianer| 
| `GIT_TOKEN` | secret | Git token related to the GIT_USERNAME | 
| `PORTAINER_URL` | variable |  Portinaer endpoint (excluded /api)| 
| `PORTAINER_ENVIRONMENT_ID` | variable | Portinaer endpoint (excluded /api)| 

---

## Deploy Reverse Proxy Configuration

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

### How to populate DEPLOY_KNOWN_HOSTS

Use the command below from a machine that already is able to connect to the remote host and use the output of this command as it is to populate the DEPLOY_KNOWN_HOSTS secret. 

```bash
ssh-keyscan hostname -p port 
```
---

## Philosophy

- Git is the source of truth; no manual changes on servers.
- All configuration is expressed as code and validated with portable tooling.
- Reverse proxy automation is opt-in and safe by default.
- No secrets committed—environment variables live in `.env` or CI secrets.

With these conventions, rolling out a new homelab service is as simple as generating the repo, configuring the stack, and pushing to main. All supporting automation (validation, deployment, releases) is ready out of the box.
