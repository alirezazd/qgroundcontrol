#!/usr/bin/env python3
"""Run pre-commit checks with CI-friendly summaries."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from _bootstrap import ensure_tools_dir

ensure_tools_dir(__file__)

from common import find_repo_root, get_default_branch_ref, run_captured
from common.gh_actions import write_github_output as _write_github_output
from common.gh_actions import write_step_summary as _write_step_summary
from common.git import run_git
from common.io import chdir
from common.logging import log_error, log_info, log_ok

# pre-commit pads each verdict to the right margin with dots, or "(no files to check)";
# anchoring there keeps words inside --show-diff-on-failure output from counting.
HOOK_RESULT_RE = re.compile(r"(?:\.{3,}|\))(Passed|Failed|Skipped)$")
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run pre-commit checks.")
    parser.add_argument(
        "-c",
        "--changed",
        action="store_true",
        help="Run only on files you changed: uncommitted, untracked, and commits not yet upstream",
    )
    parser.add_argument("-i", "--install", action="store_true", help="Install pre-commit hooks")
    parser.add_argument("-u", "--update", action="store_true", help="Update hook versions")
    parser.add_argument("--ci", action="store_true", help="Enable GitHub Actions outputs")
    parser.add_argument("-o", "--output", default="", help="Write raw output to file")
    return parser.parse_args(argv)


def repo_root() -> Path:
    return find_repo_root(Path(__file__))


def ensure_precommit_available() -> bool:
    return shutil.which("pre-commit") is not None


def strip_ansi(value: str) -> str:
    return ANSI_ESCAPE_RE.sub("", value)


def summarize_output(output: str) -> tuple[int, int, int]:
    passed = failed = skipped = 0
    for line in output.splitlines():
        # --color=always wraps each verdict in escapes, and \b sees the closing
        # "m" as a word character: match on the stripped line or count nothing.
        match = HOOK_RESULT_RE.search(strip_ansi(line))
        if not match:
            continue
        state = match.group(1)
        if state == "Passed":
            passed += 1
        elif state == "Failed":
            failed += 1
        elif state == "Skipped":
            skipped += 1
    return passed, failed, skipped


def extract_hook_lines(output: str, *, limit: int = 40) -> list[str]:
    lines = [strip_ansi(line) for line in output.splitlines() if ".........." in line]
    return lines[:limit] or ["No results"]


def changed_files() -> list[str]:
    """Files the developer has touched, relative to the repo root.

    The working tree against HEAD, untracked files, and the commits not yet on
    the branch's upstream -- or on the default branch when there is no upstream.
    A from-ref/to-ref range alone misses the first two, and is empty for anyone
    committing straight to the default branch.
    """
    names: list[str] = []
    for cmd in (
        ["diff", "--name-only", "HEAD"],
        ["ls-files", "--others", "--exclude-standard"],
    ):
        result = run_git(*cmd)
        if result.returncode == 0:
            names.extend(result.stdout.splitlines())

    upstream = run_git("rev-parse", "--abbrev-ref", "@{upstream}")
    base = upstream.stdout.strip() if upstream.returncode == 0 else get_default_branch_ref()
    if base:
        result = run_git("diff", "--name-only", f"{base}...HEAD")
        if result.returncode == 0:
            names.extend(result.stdout.splitlines())

    # Deleted files are still named by the diffs; pre-commit rejects them.
    return sorted({name for name in names if name and Path(name).is_file()})


def build_precommit_args(args: argparse.Namespace) -> list[str]:
    """The pre-commit command line, or [] when --changed finds nothing to lint."""
    result = ["pre-commit", "run", "--show-diff-on-failure", "--color=always"]
    if not args.changed:
        result.append("--all-files")
        return result
    files = changed_files()
    if not files:
        return []
    log_info(f"Running on {len(files)} changed file(s)...")
    result.append("--files")
    result.extend(files)
    return result


def write_github_output(
    exit_code: int, passed: int, failed: int, skipped: int, summary_lines: list[str]
) -> None:
    _write_github_output(
        {
            "exit_code": str(exit_code),
            "passed": str(passed),
            "failed": str(failed),
            "skipped": str(skipped),
            "summary": "\n".join(summary_lines),
        }
    )


def write_step_summary(exit_code: int, passed: int, failed: int, skipped: int, output: str) -> None:
    parts = ["## Pre-commit Results\n"]
    parts.append("**All checks passed**\n" if exit_code == 0 else "**Some checks failed**\n")
    parts.append("| Status | Count |\n|--------|-------|")
    parts.append(f"| Passed | {passed} |")
    parts.append(f"| Failed | {failed} |")
    if skipped > 0:
        parts.append(f"| Skipped | {skipped} |")
    hook_lines = "\n".join(extract_hook_lines(output))
    parts.append(
        f"\n<details>\n<summary>Hook Results</summary>\n\n```\n{hook_lines}\n```\n</details>"
    )

    diff = run_captured(["git", "diff", "--stat"])
    if diff.stdout.strip():
        parts.append(
            f"\n<details>\n<summary>Files Modified by Hooks</summary>\n\n```\n{diff.stdout}```\n</details>"
        )

    _write_step_summary("\n".join(parts) + "\n")


def handle_install() -> int:
    log_info("Installing pre-commit and hooks...")
    from common import pip_install

    pip_install(["pre-commit"])
    subprocess.run(["pre-commit", "install"], check=True)
    subprocess.run(["pre-commit", "install", "--hook-type", "commit-msg"], check=True)
    log_ok("Pre-commit hooks installed")
    return 0


def handle_update() -> int:
    log_info("Updating pre-commit hooks...")
    subprocess.run(["pre-commit", "autoupdate"], check=True)
    log_ok("Hooks updated. Review changes in .pre-commit-config.yaml")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    with chdir(repo_root()):
        try:
            if args.install:
                return handle_install()
            if args.update:
                if not ensure_precommit_available():
                    log_error("pre-commit not found")
                    return 1
                return handle_update()

            if not ensure_precommit_available():
                log_error("pre-commit not found")
                log_info("Install with: pip install pre-commit")
                log_info("Or run: python3 ./tools/pre_commit.py --install")
                return 1

            command = build_precommit_args(args)
            if not command:
                log_ok("No changed files to lint")
                return 0
            log_info("Running pre-commit checks...")
            print()
            result = run_captured(command)
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)
            print()

            passed, failed, skipped = summarize_output(result.stdout + result.stderr)
            if args.output or os.environ.get("PRE_COMMIT_OUTPUT"):
                output_path = Path(args.output or os.environ["PRE_COMMIT_OUTPUT"])
                output_path.write_text(result.stdout + result.stderr, encoding="utf-8")
                log_info(f"Output written to: {output_path}")

            if result.returncode == 0:
                log_ok(f"All checks passed ({passed} passed)")
            else:
                log_error(f"Some checks failed ({passed} passed, {failed} failed)")

            if args.ci:
                summary_lines = extract_hook_lines(result.stdout + result.stderr)
                write_github_output(result.returncode, passed, failed, skipped, summary_lines)
                write_step_summary(
                    result.returncode, passed, failed, skipped, result.stdout + result.stderr
                )

            if result.returncode != 0:
                print()
                log_info("To fix issues locally:")
                print(
                    "  1. Fixer hooks have already rewritten the files they could; review: git diff"
                )
                print("  2. Fix what remains by hand, then stage: git add -u")
                print("  3. Amend your commit: git commit --amend --no-edit")

            return result.returncode
        except subprocess.CalledProcessError as exc:
            log_error(str(exc))
            return exc.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
