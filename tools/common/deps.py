"""Pre-flight dependency checks for external tools.

Usage:
    from common.deps import check_dependencies, require_tool

    # Check multiple tools at once, return missing list
    missing = check_dependencies(["cmake", "ninja", "clang-format"])

    # Require a single tool, raise ToolNotFoundError if missing
    path = require_tool("gcovr")
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .errors import ToolNotFoundError


def check_dependencies(tools: list[str]) -> list[str]:
    """Return list of tools not found in PATH."""
    return [t for t in tools if shutil.which(t) is None]


def find_qt_tool(name: str) -> str | None:
    """Path to one of Qt's own tools (qmllint, lupdate, ...), or None.

    Distros do not put Qt's bin dir on PATH: Fedora exposes the tools as
    ``<name>-qt6`` in /usr/bin and keeps the bare names under the prefix that
    ``qtpaths --query QT_INSTALL_BINS`` reports, Debian only the latter. The
    Qt installer relies on the caller having added its bin dir to PATH.
    """
    for candidate in (name, f"{name}-qt6"):
        path = shutil.which(candidate)
        if path is not None:
            return path
    for qtpaths in ("qtpaths6", "qtpaths"):
        if shutil.which(qtpaths) is None:
            continue
        try:
            result = subprocess.run(
                [qtpaths, "--query", "QT_INSTALL_BINS"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        bins = result.stdout.strip()
        if result.returncode == 0 and bins:
            path = shutil.which(name, path=bins)
            if path is not None:
                return path
    return None


def require_tool(name: str, *, hint: str = "") -> Path:
    """Return the path to a tool, or raise ToolNotFoundError."""
    path = shutil.which(name)
    if path is None:
        raise ToolNotFoundError(name, hint=hint or None)
    return Path(path)


def check_and_report(tools: list[str], *, exit_on_missing: bool = True) -> bool:
    """Check tools and print a summary. Returns True if all found."""
    from .logging import log_error, log_ok

    missing = check_dependencies(tools)
    if not missing:
        log_ok(f"All {len(tools)} required tools found")
        return True

    for tool in missing:
        log_error(f"Missing: {tool}")
    if exit_on_missing:
        import sys

        sys.exit(1)
    return False
