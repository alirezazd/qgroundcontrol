> **32RavenQGC** -- the QGroundControl fork for the
> [32Raven flight controller](https://github.com/alirezazd/32raven)
>
> **Build.** `just doctor` reports what the machine is missing, `just setup` installs it, pulls
> the submodules, configures and builds, and `just run` launches the result (under WSL it also
> attaches the USB radio). `just --list` has the rest; [tools/README.md](tools/README.md) the
> details.
>
> **What this fork is.** The default branch `32Raven` is rebased onto one pinned upstream release
> tag rather than tracking a branch, so the base is always a known build: currently **`v5.1.4`**
> (QGroundControl V5.1 Stable, 2026-08-30). Everything 32Raven-specific lives in `custom/`.
> Changes to upstream files are kept as separate, single-purpose commits so each can be dropped
> when upstream absorbs it; `git log v5.1.4..32Raven` lists them. Among them: 32Raven registered
> as a firmware class with a MAVLink dialect of its own, `FirmwarePlugin` hooks for a firmware
> that compiles its metadata into the ground station and does not implement every parameter,
> radio and sensor setup pages trimmed to what the board has, and a tag-driven release pipeline
> that builds every platform on GitHub Actions.
>
> Use this fork for the 32Raven ground station. Use upstream QGroundControl for general
> PX4/ArduPilot vehicles.

<p align="center">
  <img src="https://raw.githubusercontent.com/Dronecode/UX-Design/35d8148a8a0559cd4bcf50bfa2c94614983cce91/QGC/Branding/Deliverables/QGC_RGB_Logo_Horizontal_Positive_PREFERRED/QGC_RGB_Logo_Horizontal_Positive_PREFERRED.svg" alt="QGroundControl Logo" width="500">
</p>

<p align="center">
  <a href="https://github.com/alirezazd/qgroundcontrol/releases/latest"><img src="https://img.shields.io/github/v/release/alirezazd/qgroundcontrol?include_prereleases&label=32RavenQGC" alt="Latest Release"></a>
  <a href=".github/COPYING.md"><img src="https://img.shields.io/github/license/alirezazd/qgroundcontrol" alt="License"></a>
  <a href="https://github.com/alirezazd/qgroundcontrol/actions/workflows/linux.yml?query=branch%3A32Raven"><img src="https://github.com/alirezazd/qgroundcontrol/actions/workflows/linux.yml/badge.svg?branch=32Raven" alt="Linux Build"></a>
  <a href="https://github.com/alirezazd/qgroundcontrol/actions/workflows/release.yml"><img src="https://github.com/alirezazd/qgroundcontrol/actions/workflows/release.yml/badge.svg" alt="Release"></a>
</p>

**QGroundControl** (QGC) is a Ground Control Station (GCS) for UAVs, providing full flight control
and mission planning for any *MAVLink-enabled* drone, including *PX4* and *ArduPilot* platforms.

## Features

- **Mission planning** — plan, edit, and fly autonomous waypoint, survey, and structure-scan missions.
- **Live Fly View** — real-time flight display with map, instruments, and full vehicle telemetry.
- **Vehicle setup** — guided wizards for sensor calibration, radio, flight modes, and power.
- **Parameter tuning** — inspect and edit every vehicle parameter through the Fact System.
- **Video streaming** — GStreamer-based UDP RTP / RTSP video with recording in the Flight Display.
- **Multi-vehicle** — connect to and monitor multiple vehicles simultaneously.
- **MAVLink tooling** — built-in MAVLink Inspector, console, and log download/analysis.
- **Cross-platform** — Windows, macOS, Linux, Android, and iOS from a single codebase.

## Download

Grab the latest build for your platform, or see all assets on the
[releases page](https://github.com/alirezazd/qgroundcontrol/releases/latest):

<p align="center">
  <a href="https://github.com/alirezazd/qgroundcontrol/releases/latest/download/32RavenQGC-installer-AMD64.exe"><img src="https://img.shields.io/badge/Windows-0078D6?logo=windows&logoColor=white" alt="Windows"></a>
  <a href="https://github.com/alirezazd/qgroundcontrol/releases/latest/download/32RavenQGC-installer-ARM64.exe"><img src="https://img.shields.io/badge/Windows%20on%20ARM-0078D6?logo=windows&logoColor=white" alt="Windows on ARM"></a>
  <a href="https://github.com/alirezazd/qgroundcontrol/releases/latest/download/32RavenQGC.dmg"><img src="https://img.shields.io/badge/macOS-000000?logo=apple&logoColor=white" alt="macOS"></a>
  <a href="https://github.com/alirezazd/qgroundcontrol/releases/latest/download/32RavenQGC-x86_64.AppImage"><img src="https://img.shields.io/badge/Linux-FCC624?logo=linux&logoColor=black" alt="Linux (AppImage)"></a>
  <a href="https://github.com/alirezazd/qgroundcontrol/releases/latest/download/32RavenQGC-aarch64.AppImage"><img src="https://img.shields.io/badge/Linux%20aarch64-FCC624?logo=linux&logoColor=black" alt="Linux aarch64 (AppImage)"></a>
  <a href="https://github.com/alirezazd/qgroundcontrol/releases/latest/download/32RavenQGC.apk"><img src="https://img.shields.io/badge/Android-3DDC84?logo=android&logoColor=white" alt="Android"></a>
</p>

Every release carries `SHA256SUMS` for the assets above. The macOS build is not notarized: open it
from System Settings, Privacy & Security, Open Anyway. The APK is signed with this fork's key, so
each release installs over the previous one.

## Links

- [32Raven flight controller](https://github.com/alirezazd/32raven) / [The 32Raven Handbook](https://alirezazd.github.io/32raven/)
- [Issues](https://github.com/alirezazd/qgroundcontrol/issues)
- [Upstream QGroundControl](https://github.com/mavlink/qgroundcontrol): [User Manual](https://docs.qgroundcontrol.com/en/), [Developer Guide](https://dev.qgroundcontrol.com/en/), [Dronecode Discord](https://discord.com/channels/1022170275984457759/1022185820683255908)
- [Security Policy](.github/SECURITY.md)
- [Code of Conduct](.github/CODE_OF_CONDUCT.md)
- [License](.github/COPYING.md)

## Contributing

See [AGENTS.md](AGENTS.md) for the build, test and lint commands and the coding conventions, and
[.github/CONTRIBUTING.md](.github/CONTRIBUTING.md) for the architecture patterns. Changes that are
not 32Raven-specific belong upstream, in
[mavlink/qgroundcontrol](https://github.com/mavlink/qgroundcontrol).
