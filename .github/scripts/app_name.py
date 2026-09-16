#!/usr/bin/env python3
"""Report the application name a checkout builds (QGC_APP_NAME).

CMake names every deliverable after the project -- the binary, the AppImage,
the DMG, the installer -- and a custom overlay renames the project through
QGC_APP_NAME in its CustomOverrides.cmake. CI paths that assume "QGroundControl"
therefore break on every custom build; this is the one place they ask instead.

    python3 .github/scripts/app_name.py            # prints the name
    python3 .github/scripts/app_name.py --github   # also QGC_APP_NAME=<name> to $GITHUB_ENV
                                                   # and app_name=<name> to $GITHUB_OUTPUT

The overlay directory is QGC_CUSTOM_DIR (cmake/CustomOptions.cmake), "custom"
by default; without one, or without an override in it, the name is upstream's.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from ci_bootstrap import ensure_tools_dir

ensure_tools_dir(__file__)

from common.gh_actions import append_github_env, write_github_output

DEFAULT_APP_NAME = "QGroundControl"
CUSTOM_DIR = "custom"
_OVERRIDE_RE = re.compile(r'^\s*set\(\s*QGC_APP_NAME\s+"([^"]+)"', re.M)


def app_name(repo_root: Path, custom_dir: str = CUSTOM_DIR) -> str:
    """QGC_APP_NAME from the overlay's CustomOverrides.cmake, else the upstream name."""
    overrides = repo_root / custom_dir / "cmake" / "CustomOverrides.cmake"
    if not overrides.is_file():
        return DEFAULT_APP_NAME
    match = _OVERRIDE_RE.search(overrides.read_text(encoding="utf-8", errors="replace"))
    return match.group(1) if match else DEFAULT_APP_NAME


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report the application name a checkout builds (QGC_APP_NAME)."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="checkout to inspect (default: this script's repository)",
    )
    parser.add_argument(
        "--custom-dir", default=CUSTOM_DIR, help=f"overlay directory (default: {CUSTOM_DIR})"
    )
    parser.add_argument(
        "--github",
        action="store_true",
        help="export QGC_APP_NAME to $GITHUB_ENV and app_name to $GITHUB_OUTPUT",
    )
    args = parser.parse_args(argv)

    name = app_name(args.repo_root, args.custom_dir)
    print(name)
    if args.github:
        append_github_env({"QGC_APP_NAME": name})
        write_github_output({"app_name": name})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
