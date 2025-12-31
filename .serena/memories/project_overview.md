Project: hs-service-template (Cookiecutter template for homelab services).
Purpose: scaffold Docker Compose-based services wired for Traefik, Homepage, Dokploy, Uptime Kuma.
Layout: root README (template usage), cookiecutter.json defaults; generated repo lives in {{cookiecutter.service_name}}/ containing docker-compose.yml, .env.example, ci/ scripts, .gitleaks.toml, service README.
Tech stack: Docker Compose YAML, POSIX sh scripts, Markdown docs, .env files; semantic-release for versioning in generated repos; gitleaks for secrets scanning.
Placeholders: Jinja-style {{ cookiecutter.* }} must be preserved in template files.
Testing: no unit/integration tests; main validation via ./ci/check.sh (file/var presence + gitleaks).