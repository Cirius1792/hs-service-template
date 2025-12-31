Validation: cd {{cookiecutter.service_name}} && ./ci/check.sh
Secrets scan (manual/targeted): cd {{cookiecutter.service_name}} && gitleaks detect --source . --no-git [--report-path report.json]
Release: cd {{cookiecutter.service_name}} && ./ci/release.sh (requires semantic-release)
Release dry-run: semantic-release --dry-run
Run stack locally: cd {{cookiecutter.service_name}} && docker compose up -d
Tear down: docker compose down
Logs: docker compose logs -f {{cookiecutter.service_name}}
Health check locally: curl -f http://localhost:{{cookiecutter.default_port}}
Env var check: grep -E "^(SERVICE_NAME|BASE_DOMAIN|TZ|PUID|PGID)=" .env.example