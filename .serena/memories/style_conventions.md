Shell: use /usr/bin/env sh + set -e, POSIX syntax (no bashisms), two-space indent, quote variables/paths, stderr for errors, exit non-zero on failure, avoid sudo.
YAML/Compose: version "3.9", two-space indent, keep proxy network external, use lower-case service keys, explicit volumes (/data/${SERVICE_NAME}), labels for traefik/homepage, simple CMD healthcheck, keep env keys aligned with .env.example.
Docs: concise Italian tone, sentence-case headings, env var tables, backticks for commands, avoid secrets.
Naming: uppercase env vars, snake_case shell vars, kebab-case filenames.
Template safety: preserve {{ cookiecutter.* }} placeholders and spacing; update cookiecutter.json and downstream references together.
Git: Conventional Commits, minimal diffs, avoid committing .env, compiled or Docker data.