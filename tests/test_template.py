"""Integration tests for the Cookiecutter template."""

from __future__ import annotations

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
