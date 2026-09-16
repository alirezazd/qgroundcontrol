"""Tests for tools/setup/wsl_usb_attach.py."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from ._helpers import load_script_module

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

wsl_usb = load_script_module("setup/wsl_usb_attach.py", "wsl_usb_attach")

USBIPD_LIST = """\
Connected:
BUSID  VID:PID    DEVICE                                                        STATE
2-6    8087:0029  Intel(R) Wireless Bluetooth(R)                                Not shared
9-3    19f7:000a  USB Input Device, RODE AI-1                                   Not shared
9-4    10c4:ea60  CP2102 USB to UART Bridge Controller                          Attached
9-5    0403:6001  FT232R USB UART                                               Shared
9-6    1a86:7523  USB-SERIAL CH340                                              Shared (forced)

Persisted:
GUID                                  DEVICE
"""


def test_parse_list_reads_every_connected_row() -> None:
    devices = wsl_usb.parse_list(USBIPD_LIST.replace("\n", "\r\n"))
    assert [d.busid for d in devices] == ["2-6", "9-3", "9-4", "9-5", "9-6"]
    cp2102 = devices[2]
    assert (cp2102.vidpid, cp2102.state) == ("10c4:ea60", "Attached")
    assert cp2102.name == "CP2102 USB to UART Bridge Controller"
    assert devices[4].state == "Shared (forced)" and devices[4].bound


def test_plan_attaches_bound_and_repairs_stale() -> None:
    devices = wsl_usb.parse_list(USBIPD_LIST)
    # The kernel has the FT232R already and nothing else.
    actions = wsl_usb.plan(devices, present={"0403:6001"})
    assert [(a, d.busid) for a, d in actions] == [
        ("reattach", "9-4"),  # Attached per usbipd, absent in the kernel: dead VM
        ("attach", "9-5"),  # bound: attach regardless of what is present
        ("attach", "9-6"),
    ]


def test_plan_leaves_a_live_attachment_alone() -> None:
    devices = wsl_usb.parse_list(USBIPD_LIST)
    actions = wsl_usb.plan(devices, present={"10c4:ea60"})
    assert [(a, d.busid) for a, d in actions] == [("attach", "9-5"), ("attach", "9-6")]


def test_main_is_silent_off_wsl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wsl_usb, "WSL_GPU_DEVICE", tmp_path / "dxg")
    assert wsl_usb.main([]) == 0


def test_main_hints_without_usbipd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "dxg").write_text("", encoding="utf-8")
    monkeypatch.setattr(wsl_usb, "WSL_GPU_DEVICE", tmp_path / "dxg")
    monkeypatch.setattr(wsl_usb, "ensure_interop", lambda: True)
    monkeypatch.setattr(wsl_usb, "find_usbipd", lambda: None)
    assert wsl_usb.main([]) == 0
    assert "winget install dorssel.usbipd-win" in capsys.readouterr().err


def test_ensure_interop_true_when_registered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "WSLInterop").write_text("", encoding="utf-8")
    monkeypatch.setattr(wsl_usb, "BINFMT_DIR", tmp_path)
    assert wsl_usb.ensure_interop() is True


def test_ensure_interop_registers_through_sudo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(wsl_usb, "BINFMT_DIR", tmp_path)

    def fake_run(cmd, **kwargs):
        assert cmd[:3] == ["sudo", "-n", "tee"] and kwargs["input"].startswith(":WSLInterop:")
        (tmp_path / "WSLInterop").write_text("", encoding="utf-8")  # what the kernel does
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(wsl_usb.subprocess, "run", fake_run)
    assert wsl_usb.ensure_interop() is True
    assert "re-registered" in capsys.readouterr().out


def test_ensure_interop_hints_when_sudo_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(wsl_usb, "BINFMT_DIR", tmp_path)
    monkeypatch.setattr(
        wsl_usb.subprocess, "run", lambda cmd, **_k: subprocess.CompletedProcess(cmd, 1, "", "no")
    )
    assert wsl_usb.ensure_interop() is False
    assert "/etc/binfmt.d/WSLInterop.conf" in capsys.readouterr().err
