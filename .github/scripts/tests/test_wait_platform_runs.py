"""Tests for wait_platform_runs.py."""

from __future__ import annotations

import pytest
from wait_platform_runs import Run, latest_per_workflow, wait

WANTED = ["Linux", "Windows"]


def run(name: str, run_id: int, status: str, conclusion: str | None, created: str = "t1") -> Run:
    return Run(
        workflow=name, run_id=run_id, status=status, conclusion=conclusion, created_at=created
    )


def test_latest_per_workflow_prefers_the_rerun() -> None:
    runs = [
        run("Linux", 1, "completed", "failure", "2026-09-16T01:00:00Z"),
        run("Linux", 2, "in_progress", None, "2026-09-16T02:00:00Z"),
        run("Docs", 3, "completed", "success"),
    ]
    latest = latest_per_workflow(runs, WANTED)
    assert set(latest) == {"Linux"}
    assert latest["Linux"].run_id == 2


def test_wait_returns_ids_once_all_green() -> None:
    polls = iter(
        [
            [run("Linux", 1, "in_progress", None)],
            [run("Linux", 1, "in_progress", None), run("Windows", 2, "queued", None)],
            [run("Linux", 1, "completed", "success"), run("Windows", 2, "completed", "success")],
        ]
    )
    clock = iter(range(0, 1000, 10))
    slept: list[float] = []
    ids = wait(
        WANTED,
        lambda: next(polls),
        timeout_s=600,
        poll_s=30,
        startup_grace_s=300,
        sleep=slept.append,
        now=lambda: next(clock),
    )
    assert ids == {"Linux": 1, "Windows": 2}
    assert slept == [30, 30]


def test_wait_fails_fast_on_a_failed_platform() -> None:
    with pytest.raises(RuntimeError, match="Windows \\(run 2: failure\\)"):
        wait(
            WANTED,
            lambda: [
                run("Linux", 1, "in_progress", None),
                run("Windows", 2, "completed", "failure"),
            ],
            timeout_s=600,
            poll_s=30,
            startup_grace_s=300,
            sleep=lambda _s: None,
            now=lambda: 0,
        )


def test_wait_reports_a_workflow_that_never_started() -> None:
    clock = iter([0, 400, 800])
    with pytest.raises(RuntimeError, match="no run for Windows"):
        wait(
            WANTED,
            lambda: [run("Linux", 1, "in_progress", None)],
            timeout_s=6000,
            poll_s=30,
            startup_grace_s=300,
            sleep=lambda _s: None,
            now=lambda: next(clock),
        )


def test_wait_times_out() -> None:
    clock = iter([0, 100, 7000])
    with pytest.raises(RuntimeError, match="timed out waiting for Linux, Windows"):
        wait(
            WANTED,
            lambda: [run("Linux", 1, "in_progress", None), run("Windows", 2, "queued", None)],
            timeout_s=6000,
            poll_s=30,
            startup_grace_s=300,
            sleep=lambda _s: None,
            now=lambda: next(clock),
        )
