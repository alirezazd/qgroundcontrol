"""Tests for common.deps module."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from common.deps import check_dependencies, find_qt_tool, require_tool
from common.errors import ToolNotFoundError

from ._helpers import completed


class TestCheckDependencies:
    """Tests for check_dependencies()."""

    def test_all_found(self):
        """Returns empty list when all tools exist."""
        with patch.object(shutil, "which", return_value="/usr/bin/python3"):
            assert check_dependencies(["python3", "cmake"]) == []

    def test_some_missing(self):
        """Returns names of missing tools."""

        def fake_which(name):
            return "/usr/bin/cmake" if name == "cmake" else None

        with patch.object(shutil, "which", side_effect=fake_which):
            result = check_dependencies(["cmake", "ninja", "gcovr"])
            assert result == ["ninja", "gcovr"]

    def test_empty_list(self):
        """Empty input returns empty output."""
        assert check_dependencies([]) == []


class TestRequireTool:
    """Tests for require_tool()."""

    def test_found(self):
        """Returns Path when tool exists."""
        with patch.object(shutil, "which", return_value="/usr/bin/cmake"):
            result = require_tool("cmake")
            assert isinstance(result, Path)
            assert result == Path("/usr/bin/cmake")

    def test_not_found_raises(self):
        """Raises ToolNotFoundError when tool is missing."""
        with (
            patch.object(shutil, "which", return_value=None),
            pytest.raises(ToolNotFoundError, match="cmake"),
        ):
            require_tool("cmake")

    def test_hint_in_message(self):
        """Hint text appears in the error message."""
        with (
            patch.object(shutil, "which", return_value=None),
            pytest.raises(ToolNotFoundError, match="pip install"),
        ):
            require_tool("gcovr", hint="pip install gcovr")


def test_find_qt_tool_prefers_bare_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name, path=None: f"/usr/bin/{name}")
    assert find_qt_tool("qmllint") == "/usr/bin/qmllint"


def test_find_qt_tool_accepts_fedora_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name, path=None: "/usr/bin/qmllint-qt6" if name == "qmllint-qt6" else None,
    )
    assert find_qt_tool("qmllint") == "/usr/bin/qmllint-qt6"


def test_find_qt_tool_falls_back_to_qt_install_bins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = tmp_path / "qmllint"
    tool.write_text("", encoding="utf-8")
    tool.chmod(0o755)
    real_which = shutil.which

    def which(name: str, path: str | None = None) -> str | None:
        if path is not None:
            return real_which(name, path=path)
        return "/usr/bin/qtpaths6" if name == "qtpaths6" else None

    monkeypatch.setattr(shutil, "which", which)
    with patch("common.deps.subprocess.run", return_value=completed(f"{tmp_path}\n")):
        assert find_qt_tool("qmllint") == str(tool)


def test_find_qt_tool_none_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name, path=None: None)
    assert find_qt_tool("qmllint") is None
