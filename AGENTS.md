# AGENTS

1. Scope: this file governs the whole repository; no nested AGENTS overrides exist.
2. Purpose: guide agentic contributors for this homelab service template repository.
3. Cursor/Copilot rules: none present (.cursor/, .cursorrules, .github/copilot-instructions.md absent).
4. Repo type: Cookiecutter template used to scaffold homelab service repos.
5. Primary stack: Docker Compose YAML, POSIX shell scripts, Markdown docs, .env files.
6. Template variables: Jinja-style `{{ cookiecutter.* }}` placeholders must be preserved until Cookiecutter renders.
7. Generated repo root lives under `{{cookiecutter.repository_name}}/` here; adjust paths accordingly (service definitions still use `{{cookiecutter.service_name}}`).
8. Default service values come from `cookiecutter.json` (repository_name, service_name, service_group, service_icon, base_domain, default_port).
9. Outputs of Cookiecutter are intended for Dokploy + Traefik + Homepage + Uptime Kuma workflows.
10. All commands below assume execution from the generated service root (`{{cookiecutter.repository_name}}/`).

## Directory map
11. `{{cookiecutter.repository_name}}/docker-compose.yml`: service definition with Traefik/Homepage labels.
12. `{{cookiecutter.repository_name}}/.env.example`: required environment variable template.
13. `{{cookiecutter.repository_name}}/ci/check.sh`: local/CI validation script.
14. `{{cookiecutter.repository_name}}/ci/release.sh`: semantic-release wrapper.
15. `{{cookiecutter.repository_name}}/ci/semantic-release.config.js`: release config.
16. `{{cookiecutter.repository_name}}/.gitleaks.toml`: allowlist for secrets scanning.
17. `README.md` (root): explains template usage and prerequisites.
18. `{{cookiecutter.repository_name}}/README.md`: per-service variables and healthcheck summary.
19. No tests, build outputs, or compiled artifacts exist in the template.
20. No language-specific package manager files are present.

## Prerequisites
21. Git, Cookiecutter, Docker (optional for local run), sh-compatible shell.
22. CI tools: `gitleaks`, `node`, `semantic-release` expected in PATH for scripts.
23. Docker Compose v2+ required for running the stack.
24. Ensure `proxy` Docker network exists (external) before composing locally.
25. Use POSIX `sh` for scripts; avoid bash-only features.
26. Keep environment locale UTF-8; scripts assume standard GNU utilities.

## Core commands
27. Validate repository locally: `cd {{cookiecutter.repository_name}} && ./ci/check.sh`.
28. What check does: confirms required files, required vars in `.env.example`, runs `gitleaks detect --source . --no-git`.
29. If gitleaks missing, script fails with message; install before rerun.
30. Release automation: `cd {{cookiecutter.repository_name}} && ./ci/release.sh` (semantic-release).
31. Semantic-release config uses branch `main` and plugins commit-analyzer, release-notes-generator, changelog, git.
32. Generate service repo from template: `cookiecutter https://github.com/<org>/clt-hs-compose-template.git` (replace org appropriately).
33. Bring up service locally after configuring `.env`: `cd {{cookiecutter.repository_name}} && docker compose up -d`.
34. Tear down local service: `docker compose down` from same directory.
35. Inspect service logs: `docker compose logs -f {{cookiecutter.service_name}}`.
36. Single check analogue: there are no unit tests; targeted validation is `gitleaks detect --source . --no-git --report-path report.json` if needed.
37. Healthcheck expectation: HTTP GET on `http://localhost:{{ cookiecutter.default_port }}` inside container.
38. Public URL pattern: `https://${SERVICE_NAME}.${BASE_DOMAIN}`.
39. Secrets scan manually: `gitleaks detect --source . --no-git` (matches CI behavior).
40. Verify required env vars present: `grep -E "^(SERVICE_NAME|BASE_DOMAIN|TZ|PUID|PGID)=" .env.example`.
41. Conventional commits enforced socially; use `feat|fix|chore|docs|refactor|perf|test` scopes as needed.
42. No lint/format commands are provided; keep files clean and POSIX-compliant.
43. To dry-run semantic-release (if installed): `semantic-release --dry-run`.
44. If a service requires auth, document and configure it manually (no template flag).

## Cookiecutter templating rules
45. Do not resolve or hardcode `{{ cookiecutter.* }}` placeholders inside the template files.
46. Preserve brace spacing exactly; Jinja syntax is significant for Cookiecutter.
47. When adding new template fields, update `cookiecutter.json` and downstream references consistently.
48. Avoid inserting YAML anchors that might conflict with Jinja braces.
49. Keep template default values generic; no secrets or org-specific data.
50. Keep filenames stable; Cookiecutter expects given paths.
51. The template does not include an auth toggle; add custom docs/labels if you extend it.
52. Do not introduce language runtimes not present in the template without updating docs/commands.

## Code style: shell (sh)
53. Use `#!/usr/bin/env sh` shebang and `set -e` for fail-fast.
54. Prefer double-quoted variables; quote paths and strings with spaces.
55. Test commands with `command -v tool >/dev/null 2>&1` before use when optional.
56. Use `[` builtin for conditionals; avoid bashisms (arrays, `[[` , brace expansion).
57. Keep scripts small, linear, and exit with non-zero on failure.
58. Print clear errors to stderr: `echo "message" >&2`.
59. Keep indentation two spaces in scripts (consistent with existing files).
60. Avoid `sudo` inside scripts; assume user manages privileges.
61. Keep environment variables uppercase snake_case.
62. Do not source user shells; rely on explicit PATH.

## Code style: YAML / Docker Compose
63. Compose version is "3.9"; align with that.
64. Indent with two spaces; avoid tabs.
65. Quote templated env var usage (`${VAR}`) as shown.
66. Keep labels minimal; align new labels with Traefik/Homepage conventions.
67. Keep healthcheck definitions simple; prefer `CMD` array syntax.
68. Networks: leave `proxy` as external; do not redefine inside template.
69. Avoid extending compose with build contexts; template assumes prebuilt images.
70. Keep volumes paths explicit; no bind mounts without clear purpose.
71. Use lower-case service keys; match `{{ cookiecutter.service_name }}` pattern.
72. Keep `.env` keys aligned with `.env.example` and docs.

## Documentation style
73. Markdown headings in sentence case; keep tables for env vars.
74. Keep README sections concise: Description, Variables, URL, Healthcheck, Monitoring.
75. Use backticks for inline code and commands.
76. Avoid embedding secrets or real domains in docs.
77. Prefer bullet lists over long paragraphs for steps.
78. Keep language consistent (Italian currently); follow existing tone.

## Error handling & messaging
79. Scripts should exit early with clear messages when prerequisites missing.
80. Avoid silent failures; always return non-zero on checks failing.
81. When adding checks, keep output short and CI-friendly.
82. For optional tooling, print actionable install hints.
83. Ensure gitleaks failures bubble up (do not ignore exit codes).

## Secrets & security
84. Never commit real `.env` files; only `.env.example` belongs in repo.
85. Keep `.gitleaks.toml` allowlist minimal; update if new safe files added.
86. Do not store credentials, tokens, or certificates in template defaults.
87. Validate new files for secrets locally with gitleaks before committing.
88. Avoid embedding passwords in Docker labels or compose files.

## Git & change management
89. Follow Conventional Commits for all messages (e.g., `feat: ...`).
90. Do not commit generated artifacts or Docker data directories.
91. Keep diffs minimal; avoid reformatting unrelated lines.
92. No git push or tagging from agents unless explicitly requested by user.
93. Do not amend others' commits without instruction.
94. Default branch is `main`; semantic-release expects it.
95. Update docs when commands or defaults change.

## Testing guidance
96. There are no automated unit/integration tests in the template.
97. Primary validation is `./ci/check.sh` plus optional manual gitleaks run.
98. To simulate a "single test", run gitleaks focusing on a path: `gitleaks detect --source path --no-git`.
99. For compose changes, optionally run `docker compose config` to validate YAML.
100. For healthcheck edits, verify `curl -f http://localhost:<port>` succeeds inside container.
101. If adding scripts, consider adding lightweight smoke checks instead of heavy tests.

## Release process
102. semantic-release calculates version, writes `CHANGELOG.md`, and tags git (when used in generated repos).
103. `./ci/release.sh` assumes git is clean and current branch is `main`.
104. Do not modify `semantic-release.config.js` plugin order without reason.
105. Keep changelog generation on by default; users rely on it.
106. If releases are disabled for a derivative, document the change in README.

## Local development workflow
107. Steps: fill `.env` from `.env.example`, adjust `docker-compose.yml` image, run `./ci/check.sh`, then commit.
108. Verify Traefik/Homepage labels match service values and domains.
109. Ensure `proxy` network exists: `docker network ls | grep proxy`; create with `docker network create proxy` if missing.
110. For needs-auth services, document auth layer in README; template does not provision it.
111. Keep timezone consistent with `TZ` variable.
112. Use numeric UID/GID in `.env`; avoid names.
113. Keep volumes pointing to `/data/${SERVICE_NAME}` for persistence by convention.
114. Avoid adding build contexts or multi-service setups; template is single-service oriented.
115. If adding more services, replicate label patterns and env propagation.

## Formatting & linting expectations
116. No formatter configured; maintain manual two-space indentation in YAML and shell.
117. Keep lines under ~120 characters for readability.
118. Align lists vertically; avoid trailing whitespace.
119. Keep file endings with a trailing newline.
120. Imports not applicable; if adding JS/TS later, prefer ESM and sorted imports.
121. Types not present; if adding code, prefer explicit types and null checks.
122. Naming: uppercase env vars, snake_case shell vars, kebab-case filenames.
123. Error handling: short messages + non-zero exits.
124. Logging: minimal stdout noise; CI should be readable.

## Contributions & PR guidance
125. Before changes: skim `README.md` and existing scripts to match tone.
126. After changes: rerun `./ci/check.sh` and, if applicable, `docker compose config`.
127. Document new env vars in `.env.example` and README table.
128. Mention behavioral changes in commit messages and PR description.
129. Keep AGENTS.md updated when workflows change.
130. Prefer small, isolated commits per concern.

## File handling rules
131. Do not edit `cookiecutter.json` values carelessly; they shape rendered repos.
132. Preserve placeholder braces in filenames if introduced.
133. Avoid adding binary files or large assets.
134. Keep `.gitleaks.toml` allowlist paths explicit; no globs unless needed.
135. Maintain executable bit on shell scripts (`chmod +x`).
136. Use LF line endings; avoid CRLF.
137. When adding new scripts, place under `ci/` if used by automation.
138. Keep README examples in sync with scripts and compose defaults.
139. Use English or Italian consistently within a file; match surrounding language.
140. Keep AGENTS instructions in sync with repo realities; update after major changes.

## Troubleshooting tips
141. If `./ci/check.sh` says missing files, ensure you are in generated root and files exist.
142. If gitleaks fails, review findings and extend `.gitleaks.toml` sparingly.
143. If semantic-release missing, install globally (`npm i -g semantic-release @semantic-release/{commit-analyzer,release-notes-generator,changelog,git}`) or run via npx.
144. If docker compose fails on network, create `proxy` network manually.
145. Healthcheck failures often indicate wrong internal port; update `{{ cookiecutter.default_port }}` accordingly.
146. For Homepage label issues, confirm `homepage.group` and `homepage.icon` match expected values.
147. For Traefik 404s, verify DNS/BASE_DOMAIN and router rule `Host(\`${SERVICE_NAME}.${BASE_DOMAIN}\`)`.
148. For permission issues, ensure `PUID/PGID` match host user.
149. When in doubt, regenerate from template and diff changes to isolate problems.
150. Keep this AGENTS file close to ~150 lines; update deliberately when workflows evolve.
