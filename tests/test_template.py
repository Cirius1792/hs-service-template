"""Integration tests for the Cookiecutter template."""

from __future__ import annotations

import tomllib
from pathlib import Path

from cookiecutter.main import cookiecutter  # type: ignore[import]

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


def test_given_cruft_workflow_when_project_is_rendered_then_it_reuses_git_token(
    tmp_path: Path,
) -> None:
    """Given cruft workflow is rendered, then it reuses the existing GIT_TOKEN."""
    # Given
    workflow_path = ".github/workflows/cruft-update.yml"

    # When
    project = render_project(tmp_path)
    workflow = project / workflow_path
    content = workflow.read_text()

    # Then
    assert "secrets.GIT_TOKEN" in content, (
        "Must reuse existing GIT_TOKEN secret"
    )
    assert "secrets.GITEA_TOKEN" not in content, (
        "Must not reference a separate GITEA_TOKEN secret"
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


def test_readme_documents_cruft_skipped_customization_files(tmp_path: Path) -> None:
    """Generated README explains which files cruft intentionally skips."""
    project = render_project(tmp_path)

    readme = (project / "README.md").read_text()

    assert "Files intentionally skipped from template updates" in readme
    assert "`pyproject.toml` exists only to hold cruft configuration" in readme
    assert "does not make this repository a Python package" in readme
    assert "Manually compare the template version" in readme
    assert "will continue to be updated by `cruft update`" in readme

    for skipped_path in EXPECTED_CRUFT_SKIP:
        assert skipped_path in readme
