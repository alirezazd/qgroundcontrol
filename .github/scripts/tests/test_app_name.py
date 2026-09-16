"""Tests for app_name.py."""

from __future__ import annotations

from typing import TYPE_CHECKING

from _helpers import REPO_ROOT
from app_name import DEFAULT_APP_NAME, app_name, main

if TYPE_CHECKING:
    from pathlib import Path


def test_upstream_name_without_overlay(tmp_path: Path) -> None:
    assert app_name(tmp_path) == DEFAULT_APP_NAME


def test_upstream_name_when_overlay_does_not_rename(tmp_path: Path) -> None:
    overrides = tmp_path / "custom" / "cmake" / "CustomOverrides.cmake"
    overrides.parent.mkdir(parents=True)
    overrides.write_text('set(QGC_ORG_NAME "Acme" CACHE STRING "Org" FORCE)\n', encoding="utf-8")
    assert app_name(tmp_path) == DEFAULT_APP_NAME


def test_overlay_rename_wins(tmp_path: Path) -> None:
    overrides = tmp_path / "custom" / "cmake" / "CustomOverrides.cmake"
    overrides.parent.mkdir(parents=True)
    overrides.write_text(
        '# set(QGC_APP_NAME "Commented" CACHE STRING "x" FORCE)\n'
        'set(QGC_APP_NAME "AcmeGCS" CACHE STRING "App Name" FORCE)\n',
        encoding="utf-8",
    )
    assert app_name(tmp_path) == "AcmeGCS"


def test_this_fork_is_named(capsys) -> None:
    assert main(["--repo-root", str(REPO_ROOT)]) == 0
    assert capsys.readouterr().out.strip() == "32RavenQGC"


def test_github_mode_exports(tmp_path: Path, monkeypatch, capsys) -> None:
    env_file, out_file = tmp_path / "env", tmp_path / "out"
    monkeypatch.setenv("GITHUB_ENV", str(env_file))
    monkeypatch.setenv("GITHUB_OUTPUT", str(out_file))
    assert main(["--repo-root", str(tmp_path), "--github"]) == 0
    assert env_file.read_text(encoding="utf-8").strip() == f"QGC_APP_NAME={DEFAULT_APP_NAME}"
    assert out_file.read_text(encoding="utf-8").strip() == f"app_name={DEFAULT_APP_NAME}"
