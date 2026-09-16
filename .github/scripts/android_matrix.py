#!/usr/bin/env python3
"""Emit the android.yml build matrix as a JSON 'include' list.

Two legs: linux builds the APK that ships (every ABI, signed with the
release keystore), linux-emulator builds x86_64 and installs and launches
it on an emulator. Upstream also builds from mac and windows hosts to keep
those developer setups working; this fork builds Android from Linux only.

Runner selection stays in the workflow: each leg carries `runson_runner`
(RunsOn runner name, empty for GitHub-hosted-only legs) and `fallback_runner`,
combined by the job's `runs-on` expression.
"""

from __future__ import annotations

import argparse
import json
import sys

from ci_bootstrap import ensure_tools_dir

ensure_tools_dir(__file__)

from common.gh_actions import write_github_output

Leg = dict[str, str | bool]

LINUX_JOB: Leg = {
    "host": "linux",
    "arch": "linux_gcc_64",
    "qt_host_path": "gcc_64",
    "shell": "bash",
    "primary": True,
    "emulator": False,
    "runson_runner": "linux-x64-builder",
    "fallback_runner": "ubuntu-latest",
}

LINUX_EMULATOR_JOB: Leg = {
    "host": "linux-emulator",
    "qt_host": "linux",
    "arch": "linux_gcc_64",
    "qt_host_path": "gcc_64",
    "shell": "bash",
    "primary": False,
    "emulator": True,
    "runson_runner": "linux-x64-emulator",
    "fallback_runner": "ubuntu-latest",
}


def build_matrix() -> list[Leg]:
    """Return the matrix include-list."""
    return [LINUX_JOB, LINUX_EMULATOR_JOB]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    include = build_matrix()
    serialized = json.dumps(include, separators=(",", ":"))
    write_github_output({"include": serialized})
    print(f"include={serialized}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
