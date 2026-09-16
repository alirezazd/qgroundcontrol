#!/usr/bin/env python3
"""Forward every usbipd-bound USB device into this WSL instance (`just run`).

WSL2 cannot see Windows USB devices; usbipd-win forwards them one at a time,
and an attachment dies with the WSL VM (`wsl --shutdown`, a reboot) while
usbipd keeps reporting the device as "Attached" to the old instance. This
attaches everything the user has `usbipd bind`-ed -- that is the one-time,
admin step and the whole statement of intent -- and repairs stale attachments.

Off WSL, or without usbipd-win, it exits 0 after a hint so `just run` still
launches; it never blocks the app for a device that is not plugged in.

    python3 tools/setup/wsl_usb_attach.py            # attach what is bound
    python3 tools/setup/wsl_usb_attach.py --list     # show what usbipd sees

Stdlib-only, like the rest of tools/setup.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

WSL_GPU_DEVICE = Path("/dev/dxg")  # present on WSL2 only
USBIPD_CANDIDATES = (
    Path("/mnt/c/Program Files/usbipd-win/usbipd.exe"),
    Path("/mnt/c/Program Files (x86)/usbipd-win/usbipd.exe"),
)
SYSFS_USB = Path("/sys/bus/usb/devices")
# binfmt_misc entry that lets WSL run Windows executables; systemd-binfmt can
# drop it at boot (it re-registers only /usr/lib/binfmt.d and /etc/binfmt.d).
BINFMT_DIR = Path("/proc/sys/fs/binfmt_misc")
WSL_INTEROP_RULE = ":WSLInterop:M::MZ::/init:PF"

# `usbipd list` rows: BUSID, VID:PID, description, STATE (the state is the last
# column and the only one with a closed vocabulary, so anchor on it).
_ROW_RE = re.compile(
    r"^(?P<busid>\d+-\d+(?:\.\d+)*)\s+(?P<vidpid>[0-9a-f]{4}:[0-9a-f]{4})\s+(?P<name>.*?)\s+"
    r"(?P<state>Not shared|Shared \(forced\)|Shared|Attached)\s*$"
)


@dataclass(frozen=True)
class Device:
    busid: str
    vidpid: str
    name: str
    state: str

    @property
    def bound(self) -> bool:
        return self.state.startswith("Shared")


def ensure_interop() -> bool:
    """Re-register Windows-executable support if this boot lost it; True when usable."""
    if (BINFMT_DIR / "WSLInterop").exists():
        return True
    try:
        result = subprocess.run(
            ["sudo", "-n", "tee", str(BINFMT_DIR / "register")],
            input=WSL_INTEROP_RULE + "\n",
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        result = None
    if result is not None and result.returncode == 0 and (BINFMT_DIR / "WSLInterop").exists():
        print("wsl-usb: re-registered WSL interop (systemd-binfmt had dropped it)")
        return True
    print(
        "wsl-usb: WSL interop is not registered and sudo could not fix it -- "
        f"printf '{WSL_INTEROP_RULE}\\n' | sudo tee /etc/binfmt.d/WSLInterop.conf, "
        "then sudo systemctl restart systemd-binfmt",
        file=sys.stderr,
    )
    return False


def find_usbipd() -> Path | None:
    for candidate in USBIPD_CANDIDATES:
        if candidate.is_file():
            return candidate
    found = shutil.which("usbipd.exe")
    return Path(found) if found else None


def run_usbipd(usbipd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # cwd=/mnt/c: Windows executables refuse a UNC (\\wsl.localhost\...) working directory.
    return subprocess.run(
        [str(usbipd), *args],
        capture_output=True,
        text=True,
        cwd="/mnt/c" if Path("/mnt/c").is_dir() else None,
        timeout=90,
        check=False,
    )


def parse_list(output: str) -> list[Device]:
    """Devices in the "Connected:" section of `usbipd list`."""
    devices: list[Device] = []
    for raw in output.replace("\r", "").splitlines():
        line = raw.strip()
        if line.startswith("Persisted:"):
            break
        match = _ROW_RE.match(line)
        if match:
            devices.append(Device(**match.groupdict()))
    return devices


def attached_vidpids() -> set[str]:
    """VID:PID of every USB device the WSL kernel currently has."""
    found: set[str] = set()
    if not SYSFS_USB.is_dir():
        return found
    for dev in SYSFS_USB.iterdir():
        vendor, product = dev / "idVendor", dev / "idProduct"
        try:
            if vendor.is_file() and product.is_file():
                found.add(f"{vendor.read_text().strip()}:{product.read_text().strip()}")
        except OSError:
            continue
    return found


def plan(devices: list[Device], present: set[str]) -> list[tuple[str, Device]]:
    """(action, device) pairs: attach what is bound, re-attach what is stale."""
    actions: list[tuple[str, Device]] = []
    for device in devices:
        if device.bound:
            actions.append(("attach", device))
        elif device.state == "Attached" and device.vidpid not in present:
            actions.append(("reattach", device))
    return actions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Forward every usbipd-bound USB device into this WSL instance."
    )
    parser.add_argument("--list", action="store_true", help="print usbipd's device list and exit")
    args = parser.parse_args(argv)

    if not WSL_GPU_DEVICE.exists():
        return 0
    if not ensure_interop():
        return 0
    usbipd = find_usbipd()
    if usbipd is None:
        print(
            "wsl-usb: usbipd-win not found on Windows -- winget install dorssel.usbipd-win, "
            "then usbipd bind --busid <id> once (admin) for each device to forward",
            file=sys.stderr,
        )
        return 0
    try:
        listed = run_usbipd(usbipd, "list")
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"wsl-usb: usbipd list failed: {exc}", file=sys.stderr)
        return 0
    if listed.returncode != 0:
        print(f"wsl-usb: usbipd list failed: {listed.stderr.strip()}", file=sys.stderr)
        return 0

    devices = parse_list(listed.stdout)
    if args.list:
        for device in devices:
            print(f"{device.busid:<6} {device.vidpid}  {device.state:<16} {device.name}")
        return 0

    for action, device in plan(devices, attached_vidpids()):
        if action == "reattach":
            run_usbipd(usbipd, "detach", "--busid", device.busid)
        result = run_usbipd(usbipd, "attach", "--wsl", "--busid", device.busid)
        if result.returncode == 0:
            print(f"wsl-usb: attached {device.busid} {device.name} ({device.vidpid})")
        else:
            message = (result.stderr or result.stdout).strip().splitlines()
            print(
                f"wsl-usb: could not attach {device.busid} {device.name}: "
                f"{message[-1] if message else 'unknown error'}",
                file=sys.stderr,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
