"""Integration tests for the Cookiecutter template."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import yaml
from cookiecutter.main import cookiecutter  

TEMPLATE_ROOT = Path(__file__).resolve().parents[1]

BASE_CONTEXT = {
    "service_name": "example",
    "repository_name": "example-service",
    "service_group": "Media",
    "service_icon": "app",
    "base_domain": "example.com",
    "default_port": "8080",
    "include_proxy_config": "y",
}

EXPECTED_CRUFT_SKIP = [
    "README.md",
    "docker-compose.yml",
    "stack.env",
    "configurations/locations.ini",
    "configurations/data/**",
    "swag/proxy-confs/**",
]


def render_project(tmp_path: Path, **overrides: str) -> Path:
    """Render the template into ``tmp_path`` and return the project path."""

    context = BASE_CONTEXT.copy()
    context.update(overrides)

    cookiecutter(
        str(TEMPLATE_ROOT),
        no_input=True,
        extra_context=context,
        output_dir=str(tmp_path),
    )

    return tmp_path / context["repository_name"]


def test_given_proxy_config_enabled_when_project_is_rendered_then_proxy_assets_are_generated(
    tmp_path: Path,
) -> None:
    """Given proxy config is enabled, when rendered, then proxy assets exist."""
    # Given
    service_name = "svcproxy"
    repository_name = "svcproxy"

    # When
    project = render_project(
        tmp_path,
        service_name=service_name,
        repository_name=repository_name,
        include_proxy_config="y",
    )

    # Then
    proxy_file = project / f"swag/proxy-confs/{service_name}.subdomain.conf"
    workflow = project / ".github/workflows/deploy-swag-config.yml"
    readme = (project / "README.md").read_text()

    assert proxy_file.is_file(), "Expected proxy config to be rendered"
    assert workflow.is_file(), "Workflow should be materialized as .yml"
    assert "Included proxy file" in readme


def test_given_proxy_config_disabled_when_project_is_rendered_then_proxy_assets_are_omitted(
    tmp_path: Path,
) -> None:
    """Given proxy config is disabled, when rendered, then SWAG assets are omitted."""
    # Given
    service_name = "svcnoproxy"
    repository_name = "svcnoproxy"

    # When
    project = render_project(
        tmp_path,
        service_name=service_name,
        repository_name=repository_name,
        include_proxy_config="n",
    )

    # Then
    workflow = project / ".github/workflows/deploy-swag-config.yml"
    readme = (project / "README.md").read_text()

    assert not (project / "swag").exists(), (
        "Proxy assets should be removed when disabled"
    )
    assert workflow.is_file(), "Workflow should still exist for future enablement"
    assert "generated without a SWAG configuration file" in readme


def test_given_default_context_when_project_is_rendered_then_cruft_workflow_exists(
    tmp_path: Path,
) -> None:
    """Given the default context, when rendered, then cruft workflow exists."""
    # Given
    workflow_path = ".github/workflows/cruft-update.yml"

    # When
    project = render_project(tmp_path)

    # Then
    workflow = project / workflow_path
    assert workflow.is_file(), "cruft-update.yml should be rendered"


def test_given_default_context_when_project_is_rendered_then_cruft_workflow_uses_gitea_contexts(
    tmp_path: Path,
) -> None:
    """Generated cruft updates should target the current Gitea instance."""
    # When
    project = render_project(tmp_path)

    # Then
    workflow = (project / ".github/workflows/cruft-update.yml").read_text()
    readme = (project / "README.md").read_text()

    assert "REPO_OWNER=\"${{ gitea.repository_owner }}\"" in workflow
    assert 'PR_URL="${API_URL}/repos/${REPO_OWNER}/${REPO_NAME}/pulls"' in workflow
    assert "echo \"→ Creating PR at $PR_URL\"" in workflow
    assert "PR_GITEA_TOKEN: ${{ secrets.PR_GITEA_TOKEN }}" in workflow
    assert "secrets.GITEA_TOKEN" not in workflow
    assert "secrets.GIT_TOKEN" not in workflow
    assert "GITEA_SERVER_URL: ${{ gitea.server_url }}" in workflow
    assert "git config user.email \"cruft-bot@$GITEA_HOST\"" in workflow
    assert "cruft-bot@example.com" not in workflow
    assert "template = json.loads(cruft_file.read_text()).get(\"template\", \"\")" in workflow
    assert "echo \"requires_ssh=false\" >> \"$GITHUB_OUTPUT\"" in workflow
    assert "if: steps.template_source.outputs.requires_ssh == 'true'" in workflow
    assert "git diff --cached --quiet && git diff --quiet" in workflow
    assert "git add -A" in workflow
    assert "git commit -m \"chore: template update via cruft\"" in workflow
    assert "has_diff=false" in workflow
    assert "No file changes after cruft update" in workflow
    assert "if: steps.update.outputs.has_diff == 'true'" in workflow
    assert "gitea.cltec.dev" not in workflow
    assert "gitea.cltec.dev" not in readme


def test_given_default_context_when_project_is_rendered_then_no_template_syntax_remains(
    tmp_path: Path,
) -> None:
    """Given the default context, when rendered, then no raw Jinja syntax remains."""
    # Given
    ignored_path_parts = {".git", "__pycache__"}

    # When
    project = render_project(tmp_path)
    text_files = [
        path
        for path in project.rglob("*")
        if path.is_file()
        and ignored_path_parts.isdisjoint(path.parts)
    ]

    # Then
    for path in text_files:
        content = path.read_text()
        assert "{{ cookiecutter" not in content, (
            f"Raw Cookiecutter placeholder remains in {path.relative_to(project)}"
        )
        assert "{%" not in content, (
            f"Raw Jinja tag remains in {path.relative_to(project)}"
        )


def test_generated_pyproject_configures_cruft_skip_policy(tmp_path: Path) -> None:
    """Generated repos persist cruft skip rules for customized files."""
    project = render_project(tmp_path)

    pyproject = project / "pyproject.toml"
    assert pyproject.is_file(), "pyproject.toml should be rendered"

    data = tomllib.loads(pyproject.read_text())

    assert data == {
        "tool": {
            "cruft": {
                "skip": EXPECTED_CRUFT_SKIP,
            }
        }
    }


# ---------------------------------------------------------------------------
# Workflow YAML validation tests
# ---------------------------------------------------------------------------

_WORKFLOW_GLOB = ".github/workflows/*.yml"


def _generated_workflow_paths(project: Path) -> list[Path]:
    """Return all generated workflow .yml files, sorted."""
    return sorted(project.glob(_WORKFLOW_GLOB))


def test_generated_workflow_files_are_valid_yaml(tmp_path: Path) -> None:
    """Every generated .github/workflows/*.yml must be valid YAML."""
    project = render_project(tmp_path)
    workflow_paths = _generated_workflow_paths(project)

    assert workflow_paths, f"No workflow files found matching {_WORKFLOW_GLOB}"

    for path in workflow_paths:
        content = path.read_text()
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as exc:
            rel = path.relative_to(project)
            msg = f"{rel}: invalid YAML — {exc}"
            raise AssertionError(msg) from exc


def test_generated_workflow_files_have_no_jinja_double_braces(tmp_path: Path) -> None:
    """No {{ (Jinja double-brace) remnants in generated workflow files.

    Catches Cookiecutter escaping failures like
    ``MAP_FILE={{ '"${{ ... }}"' }}`` that survive the ``{{ cookiecutter`` check.
    """
    project = render_project(tmp_path)
    workflow_paths = _generated_workflow_paths(project)

    for path in workflow_paths:
        content = path.read_text()
        rel = path.relative_to(project)
        assert "{{ cookiecutter" not in content, (
            f"{rel}: raw Cookiecutter placeholder remains"
        )
        assert "{%" not in content, (
            f"{rel}: raw Jinja tag remains"
        )
        # Additional check: any remaining {{ }} (not ${{ }}) indicates a
        # Cookiecutter escaping failure (e.g. {{ '"${{ ... }}"' }}).
        # GitHub Actions expressions use ${{ }}, so bare {{ is never valid.
        bare_braces = re.findall(r"(?<!\$)(?<!\w){{(?!\s*%)(?!\s*#)", content)
        assert not bare_braces, (
            f"{rel}: unprocessed Jinja {{ }} found: "
            f"first at offset {content.index('{{')}"
        )


def test_generated_workflow_run_blocks_have_no_blank_lines(tmp_path: Path) -> None:
    """No blank lines inside ``run: |`` YAML literal blocks.

    Gitea bug #37115: blank lines inside ``run: |`` cause a
    ``SetJob: yaml: line N: mapping values are not allowed`` error.
    """
    project = render_project(tmp_path)
    workflow_paths = _generated_workflow_paths(project)

    for path in workflow_paths:
        content = path.read_text()
        rel = path.relative_to(project)

        in_run_block = False
        key_indent = 0
        blank_lines: list[int] = []

        for lineno, line in enumerate(content.splitlines(), 1):
            stripped = line.rstrip()
            indent = len(line) - len(line.lstrip())

            if not in_run_block:
                if stripped.endswith("run: |"):
                    in_run_block = True
                    key_indent = indent
                continue

            # A non-empty line at indent <= key_indent ends the block.
            if stripped and not stripped.isspace() and indent <= key_indent:
                in_run_block = False
                continue

            # Blank lines (empty or whitespace-only) inside the block.
            if stripped == "" or stripped.isspace():
                blank_lines.append(lineno)

        assert not blank_lines, (
            f"{rel}: blank lines inside run: | blocks at lines {blank_lines}. "
            f"Replace with '#' comments to avoid Gitea jobparser bug #37115."
        )
