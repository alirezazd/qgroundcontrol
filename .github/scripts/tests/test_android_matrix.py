"""Tests for android_matrix.py."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from android_matrix import LINUX_EMULATOR_JOB, LINUX_JOB, build_matrix, main

if TYPE_CHECKING:
    import pytest


def test_build_matrix_is_the_linux_legs() -> None:
    assert build_matrix() == [LINUX_JOB, LINUX_EMULATOR_JOB]


def test_exactly_one_leg_is_primary() -> None:
    assert [leg["host"] for leg in build_matrix() if leg["primary"]] == ["linux"]


def test_legs_carry_runner_fields() -> None:
    for leg in build_matrix():
        assert "runson_runner" in leg
        assert leg["fallback_runner"]


def test_main_writes_github_output(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output_file = tmp_path / "gha_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

    assert main([]) == 0

    content = output_file.read_text()
    assert content.startswith("include=")
    payload = json.loads(content.split("=", 1)[1])
    assert payload == [LINUX_JOB, LINUX_EMULATOR_JOB]
    assert "include=" in capsys.readouterr().out
