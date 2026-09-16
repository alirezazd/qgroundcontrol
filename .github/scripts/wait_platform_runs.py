#!/usr/bin/env python3
"""Wait for the platform build workflows of one commit and report their run ids.

A release tag triggers Linux, Windows, MacOS and Android as independent
workflow runs; the release workflow needs all four green and needs their run
ids to download what they built. This polls the Actions API for runs of the
given commit until every named workflow has a completed run, exits non-zero
as soon as one of them fails, and writes ``runs=<json name->id>`` to
$GITHUB_OUTPUT.

    python3 .github/scripts/wait_platform_runs.py --sha $GITHUB_SHA \\
        --workflows Linux Windows MacOS Android

Requires ``gh`` with a token that can read Actions (GH_TOKEN).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ci_bootstrap import ensure_tools_dir

ensure_tools_dir(__file__)

from common.gh_actions import gh_error, write_github_output

if TYPE_CHECKING:
    from collections.abc import Callable

FAILED_CONCLUSIONS = frozenset({"failure", "cancelled", "timed_out", "startup_failure"})


@dataclass(frozen=True)
class Run:
    workflow: str
    run_id: int
    status: str  # queued | in_progress | completed | ...
    conclusion: str | None
    created_at: str


def fetch_runs(repo: str, sha: str) -> list[Run]:
    """Every push-triggered workflow run of *sha*, from the Actions API."""
    result = subprocess.run(
        [
            "gh",
            "api",
            "--paginate",
            f"repos/{repo}/actions/runs?head_sha={sha}&per_page=100",
            "--jq",
            ".workflow_runs[] | {name, id, status, conclusion, created_at, event}",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    runs: list[Run] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("event") != "push":
            continue
        runs.append(
            Run(
                workflow=item["name"],
                run_id=int(item["id"]),
                status=item.get("status") or "",
                conclusion=item.get("conclusion"),
                created_at=item.get("created_at") or "",
            )
        )
    return runs


def latest_per_workflow(runs: list[Run], workflows: list[str]) -> dict[str, Run]:
    """The newest run of each wanted workflow (a re-run supersedes the first)."""
    latest: dict[str, Run] = {}
    for run in runs:
        if run.workflow not in workflows:
            continue
        current = latest.get(run.workflow)
        if current is None or run.created_at > current.created_at:
            latest[run.workflow] = run
    return latest


def wait(
    workflows: list[str],
    fetch: Callable[[], list[Run]],
    *,
    timeout_s: float,
    poll_s: float,
    startup_grace_s: float,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> dict[str, int]:
    """Run ids by workflow once all are green; raises RuntimeError on failure or timeout."""
    started = now()
    while True:
        latest = latest_per_workflow(fetch(), workflows)
        failed = [
            f"{name} (run {run.run_id}: {run.conclusion})"
            for name, run in latest.items()
            if run.status == "completed" and run.conclusion in FAILED_CONCLUSIONS
        ]
        if failed:
            raise RuntimeError("platform build failed: " + ", ".join(failed))
        elapsed = now() - started
        missing = [name for name in workflows if name not in latest]
        if missing and elapsed > startup_grace_s:
            raise RuntimeError(
                "no run for " + ", ".join(missing) + " -- the tag did not trigger the workflow"
            )
        pending = [name for name, run in latest.items() if run.status != "completed"]
        if not missing and not pending:
            return {name: latest[name].run_id for name in workflows}
        if elapsed > timeout_s:
            raise RuntimeError("timed out waiting for " + ", ".join(missing + pending))
        print(f"waiting: {', '.join(missing + pending)} ({int(elapsed)}s)", flush=True)
        sleep(poll_s)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Wait for the platform build workflows of one commit and report their run ids."
    )
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--sha", required=True)
    parser.add_argument("--workflows", nargs="+", required=True, help="workflow names to wait for")
    parser.add_argument("--timeout-minutes", type=float, default=170)
    parser.add_argument("--poll-seconds", type=float, default=120)
    parser.add_argument(
        "--startup-grace-minutes",
        type=float,
        default=15,
        help="how long a workflow may take to appear before that counts as never triggered",
    )
    args = parser.parse_args(argv)

    try:
        runs = wait(
            args.workflows,
            lambda: fetch_runs(args.repo, args.sha),
            timeout_s=args.timeout_minutes * 60,
            poll_s=args.poll_seconds,
            startup_grace_s=args.startup_grace_minutes * 60,
        )
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        gh_error(str(exc))
        return 1
    for name, run_id in runs.items():
        print(f"{name}: run {run_id}")
    write_github_output({"runs": json.dumps(runs)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
