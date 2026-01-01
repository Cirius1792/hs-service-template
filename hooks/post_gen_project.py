#!/usr/bin/env python3
"""Cookiecutter post-generation hook."""

from pathlib import Path
import shutil


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def main() -> None:
    include_proxy = "{{ cookiecutter.include_proxy_config }}".strip().lower()
    if include_proxy in {"y", "yes", "true", "1"}:
        return

    project_root = Path.cwd()
    swag_dir = project_root / "swag"

    if swag_dir.exists():
        remove_path(swag_dir)


if __name__ == "__main__":
    main()
