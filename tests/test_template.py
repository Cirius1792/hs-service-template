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


def test_proxy_enabled_generates_proxy_assets(tmp_path: Path) -> None:
    project = render_project(
        tmp_path,
        service_name="svcproxy",
        repository_name="svcproxy",
        include_proxy_config="y",
    )

    proxy_file = project / "swag/proxy-confs/svcproxy.subdomain.conf"
    assert proxy_file.is_file(), "Expected proxy config to be rendered"

    workflow = project / ".github/workflows/deploy-swag-config.yml"
    assert workflow.is_file(), "Workflow should be materialized as .yml"
    workflow_content = workflow.read_text()
    assert "{{ cookiecutter" not in workflow_content
    assert "{%" not in workflow_content

    readme = (project / "README.md").read_text()

    assert "Included proxy file" in readme


def test_proxy_disabled_omits_swag_directory(tmp_path: Path) -> None:
    project = render_project(
        tmp_path,
        service_name="svcnoproxy",
        repository_name="svcnoproxy",
        include_proxy_config="n",
    )

    assert not (project / "swag").exists(), (
        "Proxy assets should be removed when disabled"
    )

    workflow = project / ".github/workflows/deploy-swag-config.yml"
    assert workflow.is_file(), "Workflow should still exist for future enablement"

    readme = (project / "README.md").read_text()
    assert "generated without a SWAG configuration file" in readme


def test_cruft_workflow_exists(tmp_path: Path) -> None:
    """The cruft-update workflow is generated in every rendered project."""
    project = render_project(tmp_path)

    workflow = project / ".github/workflows/cruft-update.yml"
    assert workflow.is_file(), "cruft-update.yml should be rendered"

    content = workflow.read_text()
    assert "{{ cookiecutter" not in content, (
        "No raw Cookiecutter placeholders should remain"
    )
    assert "{%" not in content, "No raw Jinja tags should remain"


def test_cruft_workflow_triggers(tmp_path: Path) -> None:
    """The workflow has both schedule and manual triggers."""
    project = render_project(tmp_path)
    workflow = project / ".github/workflows/cruft-update.yml"
    content = workflow.read_text()

    assert "schedule:" in content, "Must have scheduled trigger"
    assert "cron:" in content, "Must have cron schedule"
    assert "workflow_dispatch" in content, "Must have manual trigger"


def test_cruft_workflow_targets_gitea(tmp_path: Path) -> None:
    """The PR creation step uses the correct Gitea API endpoint."""
    project = render_project(tmp_path)
    workflow = project / ".github/workflows/cruft-update.yml"
    content = workflow.read_text()

    assert "gitea.cltec.dev" in content, (
        "Must target gitea.cltec.dev API"
    )
    assert "api/v1/repos" in content, (
        "Must use Gitea API v1"
    )


def test_cruft_workflow_reuses_git_token(tmp_path: Path) -> None:
    """The workflow uses GIT_TOKEN, not a new secret."""
    project = render_project(tmp_path)
    workflow = project / ".github/workflows/cruft-update.yml"
    content = workflow.read_text()

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
