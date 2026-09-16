#!/usr/bin/env python3
"""Preflight the host for a QGroundControl build (`just doctor`).

Reports per recipe rather than one pass/fail, because the recipes have disjoint
prerequisites: `just build` needs a Qt inside the supported range and a C++
compiler, `just test` needs a build directory configured with tests, and
`just lint` needs the tools that pre-commit's system hooks shell out to. A host
set up for one is legitimately not set up for another, so --target decides
which sections gate the exit code.

Read-only: nothing is fetched, updated, or configured. To install what is
missing:  just install-deps.  For what is *outdated* (Qt minors, pip packages)
see check_deps.py -- that one talks to the network; this one does not.

Examples:
    ./tools/doctor.py                                # everything; exit 1 if any recipe is blocked
    ./tools/doctor.py --target build                 # only `just build`'s needs decide the exit code
    ./tools/doctor.py --qt-root ~/Qt/6.11.1/gcc_64   # the Qt `just configure` would be handed

Stdlib-only, like the common helpers it imports: this has to work before the
.venv exists.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from _bootstrap import ensure_tools_dir

ensure_tools_dir(__file__)

from common import find_repo_root
from common.build_config import get_build_config_value
from common.cli import add_build_dir
from common.deps import find_qt_tool
from common.logging import Color, colorize, log_error, log_ok, log_warn
from common.platform import current_platform
from common.proc import run_captured
from common.tool_version import probe_version
from configure import find_qt_cmake

if TYPE_CHECKING:
    from collections.abc import Iterable

TARGETS = ("all", "build", "test", "lint")

# tools/pyproject.toml requires-python; the tools themselves are the floor, not CMake.
PYTHON_MIN = (3, 10)

# Where a Qt prefix keeps its CMake package files, by distro layout.
_QT_LIBDIRS = ("lib", "lib64", "lib/x86_64-linux-gnu", "lib/aarch64-linux-gnu")

# Prefixes CMake searches on its own once neither qt-cmake nor a prefix path names one.
_SYSTEM_PREFIXES = (
    Path("/usr"),
    Path("/usr/local"),
    Path("/opt/homebrew"),
    Path("/opt/homebrew/opt/qt"),
    Path("/usr/local/opt/qt"),
)

# WSL2 exposes the Windows GPU through this device; WSLg renders on it via Mesa's d3d12 driver.
_WSL_GPU_DEVICE = Path("/dev/dxg")

# aqtinstall's arch for this platform's desktop Qt, for the install hint.
_AQT_ARCH = {"linux": "linux_gcc_64", "macos": "clang_64", "windows": "win64_msvc2022_64"}

_PACKAGE_VERSION_RE = re.compile(r'set\(PACKAGE_VERSION\s+"(\d+)\.(\d+)(?:\.(\d+))?"')
_QT_RANGE_OVERRIDE_RE = re.compile(r'set\(QGC_QT_(MINIMUM|MAXIMUM)_VERSION\s+"(\d+(?:\.\d+)*)"')
# The REQUIRED find_package(Qt6) block in the root CMakeLists.txt; the earlier
# `QUIET COMPONENTS Core` probe has no REQUIRED and so does not match.
_QT_REQUIRED_RE = re.compile(
    r"find_package\(\s*Qt6\b[^)]*?\bREQUIRED\b\s+COMPONENTS\s+(.*?)(?:\bOPTIONAL_COMPONENTS\b|\))",
    re.S,
)


# -- versions ----------------------------------------------------------------


def _vstr(version: Iterable[int]) -> str:
    return ".".join(str(n) for n in version)


def _vtuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def min_version_status(
    tool: str, minimum: tuple[int, ...], *, args: tuple[str, ...] = ("--version",)
) -> tuple[bool, str]:
    """(ok, detail) for a tool that must be present at or above *minimum*."""
    if not shutil.which(tool):
        return False, "not found"
    version = probe_version(tool, args=args)
    if version is None:
        return True, "version unreadable"
    if version < minimum:
        return False, f"{_vstr(version)} -- need >= {_vstr(minimum)}"
    return True, _vstr(version)


# -- host probes -------------------------------------------------------------


def tool_status(name: str) -> tuple[bool, str]:
    path = shutil.which(name)
    return path is not None, path or "not found"


def python_status() -> tuple[bool, str]:
    version = sys.version_info[:3]
    text = f"{_vstr(version)} ({sys.executable})"
    if version < PYTHON_MIN:
        return False, f"{text} -- tools/ need >= {_vstr(PYTHON_MIN)}"
    return True, text


def compiler_status() -> tuple[bool, str]:
    """(ok, detail) for the C++ compiler CMake will pick: $CXX first, then its own defaults."""
    env = os.environ.get("CXX", "").strip()
    candidates = [env] if env else ["c++", "g++", "clang++", "cl"]
    for name in candidates:
        path = shutil.which(name)
        if path is None:
            continue
        # cl prints its banner on any invocation and rejects --version; skip the probe.
        version = probe_version(name) if name != "cl" else None
        return True, f"{path} ({_vstr(version)})" if version else path
    return False, f"{' / '.join(candidates)} not found"


def gstreamer_status(minimum: tuple[int, ...]) -> tuple[bool, str]:
    """(ok, detail) for the development files FindGStreamer.cmake asks pkg-config for."""
    if not shutil.which("pkg-config"):
        return False, "pkg-config not found"
    version = probe_version("pkg-config", args=("--modversion", "gstreamer-1.0"))
    if version is None:
        return False, "gstreamer-1.0.pc not found"
    if version < minimum:
        return False, f"{_vstr(version)} -- need >= {_vstr(minimum)}"
    return True, _vstr(version)


def wslg_gpu_status() -> tuple[bool, str] | None:
    """(ok, detail) for GPU rendering under WSLg, or None off WSL.

    Fedora's Mesa carries the d3d12 driver but does not select it by itself, so
    the app lands on llvmpipe unless GALLIUM_DRIVER says otherwise. That is the
    safe default: Mesa 26.2's d3d12 driver deadlocks its render thread on
    itself after a while, so `just run` only enables it with WSL_GPU=1. Both
    states are therefore "ok"; the detail says which one is in effect.
    """
    if not _WSL_GPU_DEVICE.exists():
        return None
    driver = os.environ.get("GALLIUM_DRIVER", "")
    if driver == "d3d12":
        return True, "GALLIUM_DRIVER=d3d12 (GPU; known to deadlock on Mesa 26.2)"
    return True, (
        f"GALLIUM_DRIVER={driver or 'unset'}: llvmpipe, software rendering -- "
        "WSL_GPU=1 just run tries the D3D12 GPU driver"
    )


_WSL_INTEROP = Path("/proc/sys/fs/binfmt_misc/WSLInterop")


def wsl_interop_status() -> tuple[bool, str] | None:
    """(ok, detail) for running Windows executables from WSL, or None off WSL.

    systemd-binfmt (pulled in by qemu-user-static) re-registers only its own
    configs at boot and drops WSL's, after which usbipd.exe / winget.exe stop
    working from inside the distro. A conf file in /etc/binfmt.d makes it stick.
    """
    if not _WSL_GPU_DEVICE.exists():
        return None
    if _WSL_INTEROP.exists():
        return True, "registered"
    return False, (
        "not registered -- printf ':WSLInterop:M::MZ::/init:PF\\n' | "
        "sudo tee /etc/binfmt.d/WSLInterop.conf && sudo systemctl restart systemd-binfmt"
    )


def wsl_usb_serial_status() -> tuple[bool, str] | None:
    """(ok, detail) for a USB serial device forwarded into WSL, or None off WSL.

    Windows keeps USB to itself; usbipd-win attaches one device at a time and
    the attachment does not survive a WSL restart.
    """
    if not _WSL_GPU_DEVICE.exists():
        return None
    devices = sorted(
        str(p) for pattern in ("ttyUSB*", "ttyACM*") for p in Path("/dev").glob(pattern)
    )
    if devices:
        return True, ", ".join(devices)
    return False, (
        "none attached -- on Windows: usbipd list, usbipd bind --busid <id> (once, admin), "
        "usbipd attach --wsl --busid <id>"
    )


def serial_group_status() -> tuple[bool, str] | None:
    """(ok, detail) for membership of the group that owns /dev/tty*, or None off Linux.

    dialout on Debian and Fedora, uucp on Arch. QGC checks the same thing at
    startup and pops a dialog; here it is visible before the first launch.
    """
    if current_platform() != "linux":
        return None
    import grp  # POSIX-only module, hence the local import

    groups = set(os.getgroups())
    user = os.environ.get("USER", "")
    for name in ("dialout", "uucp"):
        try:
            entry = grp.getgrnam(name)
        except KeyError:
            continue
        if entry.gr_gid in groups:
            return True, name
        if user and user in entry.gr_mem:
            return True, f"{name} (granted; takes effect in a new session)"
        return False, f"not in {name} -- sudo usermod -aG {name} $USER, then start a new session"
    return None


# -- Qt ----------------------------------------------------------------------


@dataclass
class QtProbe:
    """Where the Qt6 CMake package was found, and how."""

    cmake_dir: Path | None = None  # <prefix>/lib/cmake/Qt6
    origin: str = ""
    notes: list[str] = field(default_factory=list)


def _qt6_cmake_dir_under(prefix: Path) -> Path | None:
    for libdir in _QT_LIBDIRS:
        candidate = prefix / libdir / "cmake" / "Qt6"
        if (candidate / "Qt6Config.cmake").is_file():
            return candidate
    return None


def _qt_install_libs() -> Path | None:
    """Library dir of the Qt on PATH, from qtpaths/qmake -- where a distro package puts it."""
    queries = (
        ("qtpaths6", ["--query", "QT_INSTALL_LIBS"]),
        ("qtpaths", ["--query", "QT_INSTALL_LIBS"]),
        ("qmake6", ["-query", "QT_INSTALL_LIBS"]),
        ("qmake", ["-query", "QT_INSTALL_LIBS"]),
    )
    for tool, args in queries:
        if shutil.which(tool) is None:
            continue
        try:
            result = run_captured([tool, *args], timeout=5)
        except (TimeoutError, OSError):
            continue
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    return None


def find_qt6(qt_root: Path | None) -> QtProbe:
    """Locate the Qt6 CMake package the way `just configure` will.

    The order mirrors configure.py's find_qt_cmake, then CMake's own fallbacks
    once that returns nothing: the explicit root, QT_ROOT_DIR / Qt6_DIR /
    CMAKE_PREFIX_PATH, the qt-cmake install trees, the Qt on PATH, and finally
    the system prefixes.
    """
    probe = QtProbe()
    if qt_root is not None:
        found = _qt6_cmake_dir_under(qt_root)
        if found:
            return QtProbe(found, f"--qt-root {qt_root}")
        probe.notes.append(f"--qt-root {qt_root} has no Qt6Config.cmake, searched elsewhere")

    for var in ("QT_ROOT_DIR", "Qt6_DIR", "CMAKE_PREFIX_PATH"):
        for entry in os.environ.get(var, "").split(os.pathsep):
            if not entry:
                continue
            path = Path(entry)
            found = path if (path / "Qt6Config.cmake").is_file() else _qt6_cmake_dir_under(path)
            if found:
                return QtProbe(found, f"${var}", probe.notes)

    qt_cmake = find_qt_cmake(None)
    if qt_cmake is not None:
        found = _qt6_cmake_dir_under(qt_cmake.parent.parent)
        if found:
            return QtProbe(found, str(qt_cmake), probe.notes)

    libs = _qt_install_libs()
    if libs is not None and (libs / "cmake" / "Qt6" / "Qt6Config.cmake").is_file():
        return QtProbe(libs / "cmake" / "Qt6", "qtpaths/qmake on PATH", probe.notes)

    for prefix in _SYSTEM_PREFIXES:
        found = _qt6_cmake_dir_under(prefix)
        if found:
            return QtProbe(found, f"system prefix {prefix}", probe.notes)
    return probe


def qt_install_hint(repo_root: Path) -> str:
    """How to put the configured Qt where the justfile's default QT_DIR expects it.

    install_qt.py finds aqt on PATH, so it is run from the tools venv (whose
    `qt` extra is aqtinstall) rather than bare -- bare, pip_install drops aqt
    into a .venv/bin that is not on PATH and the script exits.
    """
    from setup.install_dependencies._common import detect_platform

    # The Fedora list carries Qt itself (see _packages.py); no other platform's does.
    if detect_platform() == "fedora":
        return "just install-deps --category qt, or point QT_DIR at an existing install"
    start = repo_root / "CMakeLists.txt"
    wanted = get_build_config_value("qt.version", "", start=start)
    modules = get_build_config_value("qt.modules", "", start=start)
    arch = _AQT_ARCH.get(current_platform(), "linux_gcc_64")
    script = (
        f"python3 tools/setup/install_qt.py install --version {wanted} --arch {arch} "
        f'--modules "{modules}" --outdir ~/Qt'
    )
    if shutil.which("uv"):
        return f"uv run --project tools --extra qt {script}, or point QT_DIR at an existing install"
    return f"pipx install aqtinstall, then {script}, or point QT_DIR at an existing install"


def qt_version(cmake_dir: Path) -> tuple[int, ...] | None:
    """Version from the package's own ConfigVersion file (6.x moves the value into an Impl include)."""
    for name in ("Qt6ConfigVersionImpl.cmake", "Qt6ConfigVersion.cmake"):
        path = cmake_dir / name
        if not path.is_file():
            continue
        match = _PACKAGE_VERSION_RE.search(path.read_text(encoding="utf-8", errors="replace"))
        if match:
            return tuple(int(g) for g in match.groups() if g is not None)
    return None


def qt_version_range(repo_root: Path) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """(minimum, maximum) find_package(Qt6) will accept, inclusive.

    build-config.json is the default; a custom overlay may FORCE either bound in
    its CustomOverrides.cmake (this fork widens the maximum), and that wins.
    """
    start = repo_root / "CMakeLists.txt"
    minimum = get_build_config_value("qt.minimum_version", "6.0.0", start=start)
    maximum = get_build_config_value("qt.version", "6.99.99", start=start)
    overrides = repo_root / "custom" / "cmake" / "CustomOverrides.cmake"
    if overrides.is_file():
        for bound, value in _QT_RANGE_OVERRIDE_RE.findall(
            overrides.read_text(encoding="utf-8", errors="replace")
        ):
            if bound == "MINIMUM":
                minimum = value
            else:
                maximum = value
    return _vtuple(minimum), _vtuple(maximum)


def qt_required_components(cmakelists: Path) -> list[str]:
    """The COMPONENTS of the REQUIRED find_package(Qt6) in the root CMakeLists.txt."""
    match = _QT_REQUIRED_RE.search(cmakelists.read_text(encoding="utf-8", errors="replace"))
    return match.group(1).split() if match else []


_QT_DEP_RE = re.compile(r"\bQt6([A-Z][A-Za-z0-9]*)\b")


def missing_qt_components(cmake_dir: Path, components: Iterable[str]) -> list[str]:
    """Components, or their transitive dependencies, without a Qt6<Name>Config.cmake.

    Walks each package's Dependencies file the way its Config does, because
    distros split Qt differently from the installer: Fedora keeps Qt6CorePrivate
    in a separate -private-devel package, so LocationPrivate's Config is present
    and still sets Qt6_FOUND to FALSE. A dependency is reported as "Dep (via
    Component)" so the fix is obvious.
    """
    root = cmake_dir.parent
    missing: list[str] = []
    seen: set[str] = set()

    def visit(name: str, via: str | None) -> None:
        if name in seen:
            return
        seen.add(name)
        package = root / f"Qt6{name}"
        if not (package / f"Qt6{name}Config.cmake").is_file():
            missing.append(f"{name} (via {via})" if via else name)
            return
        deps_file = package / f"Qt6{name}Dependencies.cmake"
        if not deps_file.is_file():
            return
        for dep in _QT_DEP_RE.findall(deps_file.read_text(encoding="utf-8", errors="replace")):
            if dep != name:
                visit(dep, via or name)

    for component in components:
        visit(component, None)
    return missing


# -- build directory ---------------------------------------------------------


def build_cache_values(cache: Path) -> dict[str, str]:
    """NAME -> value for the ``NAME:TYPE=value`` lines of a CMakeCache.txt."""
    values: dict[str, str] = {}
    for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line.startswith(("#", "//")):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        values[key.partition(":")[0]] = value
    return values


# -- reporting ---------------------------------------------------------------


class Section:
    """A group of checks gating one recipe."""

    def __init__(self, recipe: str) -> None:
        self.recipe = recipe
        self.failed = False
        self.needs_packages = False  # a failure `just install-deps` would fix


def _fail(msg: str) -> None:
    # stderr, so `just doctor 2>/dev/null` reduces to what passed -- but the two
    # streams buffer independently off a TTY, so flush across the handover or
    # the report reads out of order when piped.
    sys.stdout.flush()
    log_error(msg, prefix="[FAIL]")
    sys.stderr.flush()


def check(section: Section, label: str, ok: bool, detail: str, *, packaged: bool = False) -> None:
    """Report one check; *packaged* marks a tool `just install-deps` installs."""
    if ok:
        log_ok(f"{label}: {detail}")
    else:
        _fail(f"{label}: {detail}")
        section.failed = True
        section.needs_packages |= packaged


def check_optional(label: str, ok: bool, detail: str) -> None:
    """Report without gating -- for tools no recipe strictly needs."""
    (log_ok if ok else log_warn)(f"{label}: {detail}")


def _heading(title: str) -> None:
    print(f"\n{colorize(title, Color.BOLD)}")


# -- sections ----------------------------------------------------------------


def report_host(repo_root: Path) -> Section:
    section = Section("every recipe")
    _heading("Host tools")
    cmake_min = _vtuple(
        get_build_config_value(
            "build.cmake_minimum_version", "3.25", start=repo_root / "CMakeLists.txt"
        )
    )
    check(section, "git", *tool_status("git"), packaged=True)
    check(section, "cmake", *min_version_status("cmake", cmake_min), packaged=True)
    check(section, "ninja", *tool_status("ninja"), packaged=True)
    check(section, "C++ compiler", *compiler_status(), packaged=True)
    check(section, "python3", *python_status(), packaged=True)
    return section


def report_build(args: argparse.Namespace, repo_root: Path) -> tuple[Section, QtProbe]:
    section = Section("just configure / just build")
    _heading("Build -- Qt and GStreamer")

    qt = find_qt6(args.qt_root)
    minimum, maximum = qt_version_range(repo_root)
    if qt.cmake_dir is None:
        for note in qt.notes:
            log_warn(note)
        check(section, "Qt6", False, f"not found -- {qt_install_hint(repo_root)}")
    else:
        # A skipped --qt-root is worth a word, not a warning: configure.py falls
        # through the same search and lands on the same Qt.
        origin = "; ".join([f"via {qt.origin}", *qt.notes])
        version = qt_version(qt.cmake_dir)
        if version is None:
            check(section, "Qt6", True, f"{qt.cmake_dir} (version unreadable, {origin})")
        else:
            in_range = minimum <= version <= maximum
            check(
                section,
                "Qt6",
                in_range,
                f"{_vstr(version)} at {qt.cmake_dir} ({origin})"
                if in_range
                else f"{_vstr(version)} at {qt.cmake_dir} -- "
                f"find_package accepts {_vstr(minimum)}...{_vstr(maximum)}",
            )
        components = qt_required_components(repo_root / "CMakeLists.txt")
        if not components:
            log_warn("Qt modules: could not read the REQUIRED component list from CMakeLists.txt")
        else:
            missing = missing_qt_components(qt.cmake_dir, components)
            check(
                section,
                "Qt modules",
                not missing,
                f"all {len(components)} required components present"
                if not missing
                else f"missing {', '.join(missing)} -- {qt_install_hint(repo_root)}",
            )

    if current_platform() == "linux":
        gst_min = _vtuple(
            get_build_config_value(
                "gstreamer.version.minimum", "1.20.0", start=repo_root / "CMakeLists.txt"
            )
        )
        ok, detail = gstreamer_status(gst_min)
        check(
            section,
            "GStreamer",
            ok,
            detail if ok else f"{detail} -- or configure with -DQGC_ENABLE_GST_VIDEOSTREAMING=OFF",
            packaged=True,
        )
    else:
        check_optional("GStreamer", True, "downloaded by CMake at configure time on this platform")

    report_build_dir(args, repo_root, qt)
    return section, qt


def report_build_dir(args: argparse.Namespace, repo_root: Path, qt: QtProbe) -> None:
    """Warn where an existing cache disagrees with what the recipes would do now.

    Nothing here gates: a stale cache is fixed by `just configure`, which the
    warnings name. The cache is the one source for what the last configure
    actually used, so this is also where a vanished Qt shows up.
    """
    cache = repo_root / args.build_dir / "CMakeCache.txt"
    if not cache.is_file():
        log_warn(f"build dir: {args.build_dir} not configured yet -- just configure")
        return
    values = build_cache_values(cache)
    generator = values.get("CMAKE_GENERATOR", "?")
    build_type = values.get("CMAKE_BUILD_TYPE", "")
    log_ok(f"build dir: {args.build_dir} ({generator}, {build_type or 'multi-config'})")
    if build_type and build_type != args.build_type:
        log_warn(
            f"build dir: cache is {build_type} but the recipes build {args.build_type} -- "
            "just configure to switch"
        )
    app_name = values.get("QGC_APP_NAME")
    if app_name and app_name != args.app_name:
        log_warn(
            f"build dir: cache defines target {app_name}, `just build` asks for {args.app_name}"
        )
    cached_qt = values.get("Qt6_DIR", "")
    if cached_qt.endswith("-NOTFOUND"):
        # What a configure that could not find Qt leaves behind.
        log_warn("build dir: the last configure found no Qt -- just configure")
    elif cached_qt and not Path(cached_qt).is_dir():
        log_warn(
            f"build dir: cache was configured against {cached_qt}, which no longer exists -- "
            "just configure once Qt is back"
        )
    elif cached_qt and qt.cmake_dir is not None and Path(cached_qt) != qt.cmake_dir:
        log_warn(
            f"build dir: cache uses {cached_qt}; the doctor found {qt.cmake_dir} -- "
            "just configure to switch"
        )


def report_test(args: argparse.Namespace, repo_root: Path, qt: QtProbe) -> Section:
    section = Section("just test")
    _heading("Test -- ctest and a test-enabled build")
    check(section, "ctest", *tool_status("ctest"), packaged=True)
    if qt.cmake_dir is not None:
        missing = missing_qt_components(qt.cmake_dir, ["Test"])
        check(
            section,
            "Qt Test module",
            not missing,
            "present" if not missing else "missing -- the unit tests link Qt6::Test",
        )
    cache = repo_root / args.build_dir / "CMakeCache.txt"
    if not cache.is_file():
        check(
            section, "tests configured", False, f"{args.build_dir} not configured -- just configure"
        )
    else:
        values = build_cache_values(cache)
        # BUILD_TESTING is what enable_testing() keys on; QGC_BUILD_TESTING is
        # forced OFF outside Debug (cmake_dependent_option), so Release caches
        # carry no tests whatever configure.py was asked for.
        enabled = values.get("BUILD_TESTING", values.get("QGC_BUILD_TESTING", "")).upper()
        check(
            section,
            "tests configured",
            enabled in ("ON", "TRUE", "1"),
            f"BUILD_TESTING={enabled or 'unset'} in {args.build_dir}"
            if enabled in ("ON", "TRUE", "1")
            else f"BUILD_TESTING={enabled or 'unset'} in {args.build_dir} -- tests only build "
            "in Debug: BUILD_TYPE=Debug just configure",
        )
    if current_platform() == "linux" and not (
        os.environ.get("DISPLAY")
        or os.environ.get("WAYLAND_DISPLAY")
        or os.environ.get("QT_QPA_PLATFORM")
        or shutil.which("xvfb-run")
    ):
        log_warn(
            "display: no DISPLAY, WAYLAND_DISPLAY or xvfb-run -- "
            "export QT_QPA_PLATFORM=offscreen before just test"
        )
    return section


def report_lint(repo_root: Path) -> Section:
    section = Section("just lint")
    _heading("Lint -- pre-commit and its system hooks")
    # Not a system package here: the tools venv has a `precommit` extra, but
    # `just lint` calls the bare name, so it has to be on PATH.
    ok, detail = tool_status("pre-commit")
    check(
        section,
        "pre-commit",
        ok,
        detail if ok else "not found -- uv tool install pre-commit (or pipx install pre-commit)",
    )
    # The clang-tidy hook runs tools/analyze.py, which fails outright without
    # the tool or a compile database -- and reads build/ regardless of BUILD_DIR.
    ok, detail = tool_status("clang-tidy")
    check(
        section,
        "clang-tidy",
        ok,
        detail if ok else "not found -- the clang-tidy hook fails",
        packaged=True,
    )
    compile_db = repo_root / "build" / "compile_commands.json"
    check(
        section,
        "compile database",
        compile_db.is_file(),
        "build/compile_commands.json"
        if compile_db.is_file()
        else "build/compile_commands.json not found -- the clang-tidy and clazy hooks read build/ "
        "regardless of BUILD_DIR: BUILD_DIR=build just configure, or symlink your build dir to it",
    )
    # These analyzers skip themselves when the tool is absent, so a host without
    # them commits clean and then fails in CI, where they are installed.
    absent = "not found -- self-skips locally, fails in CI"
    ok, detail = tool_status("clazy-standalone")
    check_optional("clazy", ok, detail if ok else absent)
    qmllint = find_qt_tool("qmllint")
    check_optional("qmllint", qmllint is not None, qmllint or absent)
    return section


def report_optional() -> None:
    _heading("Optional")
    for label, tool, why in (
        ("ccache", "ccache", "faster rebuilds"),
        ("uv", "uv", "tools/ venv and pytest"),
        ("just", "just", "the recipes themselves"),
        ("clang-format", "clang-format", "just format"),
    ):
        ok, detail = tool_status(tool)
        check_optional(f"{label} ({why})", ok, detail)
    runtime = next((r for r in ("docker", "podman") if shutil.which(r)), None)
    check_optional("container runtime (just docker)", runtime is not None, runtime or "not found")
    gpu = wslg_gpu_status()
    if gpu is not None:
        check_optional("WSLg GPU (just run)", *gpu)
    interop = wsl_interop_status()
    if interop is not None:
        check_optional("WSL interop (usbipd/winget from WSL)", *interop)
    usb = wsl_usb_serial_status()
    if usb is not None:
        check_optional("USB serial in WSL (usbipd)", *usb)
    serial = serial_group_status()
    if serial is not None:
        check_optional("serial ports (group)", *serial)
    if current_platform() == "linux":
        # Qt's default Linux speech engine; libspeechd spawns the daemon on first use,
        # so presence of the binary is the whole check. Without it Qt falls back to
        # flite, which is installed alongside, so this is a quality warning, not a gate.
        ok, detail = tool_status("speech-dispatcher")
        check_optional(
            "speech-dispatcher (voice alerts)",
            ok,
            detail if ok else "not found -- just install-deps (audio category)",
        )


# -- entry point -------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--target",
        choices=TARGETS,
        default="all",
        help="which recipe's prerequisites decide the exit code (default: all)",
    )
    parser.add_argument(
        "--qt-root",
        type=Path,
        help="Qt install prefix `just configure` passes (e.g. ~/Qt/6.11.1/gcc_64)",
    )
    add_build_dir(parser)
    parser.add_argument(
        "-t", "--build-type", default="Debug", help="build type the recipes use (default: Debug)"
    )
    parser.add_argument(
        "--app-name",
        default="QGroundControl",
        help="target `just build` asks for (default: QGroundControl)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = find_repo_root(Path(__file__))

    want_build = args.target in ("all", "build", "test")
    want_test = args.target in ("all", "test")
    want_lint = args.target in ("all", "lint")

    print(f"QGroundControl setup check\nrepo: {repo_root}")

    host = report_host(repo_root)
    selected: list[Section] = []
    qt = QtProbe()
    if want_build:
        build, qt = report_build(args, repo_root)
        selected.append(build)
    if want_test:
        selected.append(report_test(args, repo_root, qt))
    if want_lint:
        selected.append(report_lint(repo_root))
    report_optional()

    print()
    blocked = [s for s in (host, *selected) if s.failed]
    for section in selected:
        if not section.failed and not host.failed:
            log_ok(f"ready: {section.recipe}")
    for section in blocked:
        _fail(f"blocked: {section.recipe}")

    if blocked:
        lines = ["Each [FAIL] line above names its fix; then re-run:  just doctor"]
        if any(s.needs_packages for s in blocked):
            lines.insert(0, "Install the missing system packages:  just install-deps")
        print(colorize("\n" + "\n".join(lines), Color.RED, sys.stderr), file=sys.stderr)
        return 1
    nxt = "just build" if args.target in ("all", "build") else f"just {args.target}"
    print(colorize(f"\nSetup looks ready. Next: {nxt}", Color.GREEN))
    return 0


if __name__ == "__main__":
    sys.exit(main())
