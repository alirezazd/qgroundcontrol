"""Tests for tools/pre_commit.py."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from pre_commit import (
    build_precommit_args,
    changed_files,
    extract_hook_lines,
    parse_args,
    summarize_output,
)

from ._helpers import completed

if TYPE_CHECKING:
    from pathlib import Path


def test_summarize_output_counts_states() -> None:
    passed, failed, skipped = summarize_output(
        "hook-a........................Passed\nhook-b........................Failed\nhook-c........................Skipped\n"
    )
    assert (passed, failed, skipped) == (1, 1, 1)


def test_summarize_output_counts_colored_verdicts() -> None:
    colored = (
        "hook-a...........\x1b[42mPassed\x1b[m\n"
        "hook-b...........\x1b[41mFailed\x1b[m\n"
        "hook-c...........\x1b[46;30mSkipped\x1b[m\n"
    )
    assert summarize_output(colored) == (1, 1, 1)


def test_summarize_output_ignores_verdict_words_in_diffs() -> None:
    output = (
        "hook-a........................Passed\n"
        "check json.................(no files to check)Skipped\n"
        '+        assert result == "Failed"\n'
        "-    print(f'{n} Failed')\n"
    )
    assert summarize_output(output) == (1, 0, 1)


def test_extract_hook_lines_strips_ansi() -> None:
    lines = extract_hook_lines("\x1b[31mhook-a........................Failed\x1b[0m\n")
    assert lines == ["hook-a........................Failed"]


def test_build_precommit_args_all_files() -> None:
    args = parse_args([])
    with patch("pre_commit.get_default_branch_ref", return_value="master"):
        assert build_precommit_args(args)[-1] == "--all-files"


def test_build_precommit_args_changed_mode_passes_files() -> None:
    args = parse_args(["--changed"])
    with patch("pre_commit.changed_files", return_value=["a.py", "b/c.cc"]):
        built = build_precommit_args(args)
    assert built[-3:] == ["--files", "a.py", "b/c.cc"]
    assert "--all-files" not in built


def test_build_precommit_args_changed_mode_empty_means_nothing_to_run() -> None:
    args = parse_args(["--changed"])
    with patch("pre_commit.changed_files", return_value=[]):
        assert build_precommit_args(args) == []


def _git(outputs: dict[str, tuple[int, str]]):
    """Fake run_git keyed on the subcommand's first two words."""

    def run(*argv: str, **_kwargs):
        rc, out = outputs.get(" ".join(argv[:2]), (1, ""))
        return completed(out, returncode=rc)

    return run


def test_changed_files_unions_worktree_untracked_and_unpushed(tmp_path: Path, monkeypatch) -> None:
    for name in ("dirty.py", "new.py", "pushed.py"):
        (tmp_path / name).write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    outputs = {
        "diff --name-only": (0, "dirty.py\n"),  # both diff calls share the key: see below
        "ls-files --others": (0, "new.py\ngone.py\n"),
        "rev-parse --abbrev-ref": (0, "origin/32Raven\n"),
    }

    def run(*argv: str, **_kwargs):
        if argv[:2] == ("diff", "--name-only") and argv[2].endswith("...HEAD"):
            return completed("pushed.py\n")
        return _git(outputs)(*argv)

    with patch("pre_commit.run_git", side_effect=run):
        assert changed_files() == ["dirty.py", "new.py", "pushed.py"]


def test_changed_files_falls_back_to_default_branch_without_upstream(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "branch.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    seen: list[str] = []

    def run(*argv: str, **_kwargs):
        seen.append(" ".join(argv))
        if argv[:2] == ("rev-parse", "--abbrev-ref"):
            return completed("", returncode=128)
        if argv[:2] == ("diff", "--name-only") and argv[2] == "master...HEAD":
            return completed("branch.py\n")
        return completed("")

    with (
        patch("pre_commit.run_git", side_effect=run),
        patch("pre_commit.get_default_branch_ref", return_value="master"),
    ):
        assert changed_files() == ["branch.py"]
    assert "diff --name-only master...HEAD" in seen
