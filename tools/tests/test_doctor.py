"""Tests for tools/doctor.py."""

from __future__ import annotations

import json
import os
import shutil
from typing import TYPE_CHECKING

import doctor
import pytest
from doctor import (
    QtProbe,
    build_cache_values,
    find_qt6,
    main,
    min_version_status,
    missing_qt_components,
    parse_args,
    qt_install_hint,
    qt_required_components,
    qt_version,
    qt_version_range,
    serial_group_status,
    wsl_interop_status,
    wsl_usb_serial_status,
    wslg_gpu_status,
)
from setup.install_dependencies import _common as install_deps_common

from ._helpers import REPO_ROOT

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

CMAKELISTS = """\
find_package(Qt6 ${QGC_QT_MINIMUM_VERSION} QUIET COMPONENTS Core)
if(NOT Qt6_FOUND)
    message(FATAL_ERROR "Qt6 not found")
endif()

find_package(Qt6
    ${QGC_QT_MINIMUM_VERSION}...${QGC_QT_MAXIMUM_VERSION}
    REQUIRED
    COMPONENTS
        Core
        Gui
        LinguistTools
    OPTIONAL_COMPONENTS
        SerialPort
        Test
)
"""


def make_qt_tree(root: Path, version: str, components: Iterable[str]) -> Path:
    """A Qt install prefix with just the CMake package files the doctor reads."""
    cmake_dir = root / "lib" / "cmake" / "Qt6"
    cmake_dir.mkdir(parents=True)
    (cmake_dir / "Qt6Config.cmake").write_text("", encoding="utf-8")
    (cmake_dir / "Qt6ConfigVersionImpl.cmake").write_text(
        f'set(PACKAGE_VERSION "{version}")\n', encoding="utf-8"
    )
    for component in components:
        pkg = cmake_dir.parent / f"Qt6{component}"
        pkg.mkdir()
        (pkg / f"Qt6{component}Config.cmake").write_text("", encoding="utf-8")
    return cmake_dir


@pytest.fixture
def no_system_qt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blind every fallback so find_qt6 sees only what the test hands it."""
    for var in ("QT_ROOT_DIR", "Qt6_DIR", "CMAKE_PREFIX_PATH"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(doctor, "find_qt_cmake", lambda _root: None)
    monkeypatch.setattr(doctor, "_qt_install_libs", lambda: None)
    monkeypatch.setattr(doctor, "_SYSTEM_PREFIXES", ())


# -- parse_args --------------------------------------------------------------


def test_parse_args_defaults() -> None:
    args = parse_args([])
    assert args.target == "all"
    assert args.qt_root is None
    assert args.build_dir == "build"
    assert args.build_type == "Debug"
    assert args.app_name == "QGroundControl"


def test_parse_args_rejects_unknown_target() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--target", "esp32"])


# -- versions ----------------------------------------------------------------


def test_min_version_status_below_minimum(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/cmake")
    monkeypatch.setattr(doctor, "probe_version", lambda *_a, **_k: (3, 24, 9))
    ok, detail = min_version_status("cmake", (3, 25))
    assert ok is False
    assert "3.24.9" in detail
    assert "3.25" in detail


def test_min_version_status_at_minimum_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/cmake")
    monkeypatch.setattr(doctor, "probe_version", lambda *_a, **_k: (3, 25, 0))
    assert min_version_status("cmake", (3, 25)) == (True, "3.25.0")


def test_min_version_status_missing_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert min_version_status("cmake", (3, 25)) == (False, "not found")


# -- Qt ----------------------------------------------------------------------


def test_qt_required_components_skips_quiet_probe_and_optionals(tmp_path: Path) -> None:
    cmakelists = tmp_path / "CMakeLists.txt"
    cmakelists.write_text(CMAKELISTS, encoding="utf-8")
    assert qt_required_components(cmakelists) == ["Core", "Gui", "LinguistTools"]


def test_qt_required_components_reads_the_real_root() -> None:
    components = qt_required_components(REPO_ROOT / "CMakeLists.txt")
    assert "Core" in components
    assert "Test" not in components  # optional in CMakeLists.txt


def test_qt_required_components_empty_without_block(tmp_path: Path) -> None:
    cmakelists = tmp_path / "CMakeLists.txt"
    cmakelists.write_text("project(x)\n", encoding="utf-8")
    assert qt_required_components(cmakelists) == []


def test_find_qt6_prefers_explicit_root(tmp_path: Path, no_system_qt: None) -> None:
    cmake_dir = make_qt_tree(tmp_path / "qt", "6.11.1", ["Core"])
    probe = find_qt6(tmp_path / "qt")
    assert probe.cmake_dir == cmake_dir
    assert probe.origin.startswith("--qt-root")
    assert probe.notes == []


def test_find_qt6_notes_missing_root_then_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_system_qt: None
) -> None:
    cmake_dir = make_qt_tree(tmp_path / "env-qt", "6.11.1", ["Core"])
    monkeypatch.setenv("QT_ROOT_DIR", str(tmp_path / "env-qt"))
    probe = find_qt6(tmp_path / "missing")
    assert probe.cmake_dir == cmake_dir
    assert probe.origin == "$QT_ROOT_DIR"
    assert probe.notes and "missing" in probe.notes[0]


def test_find_qt6_accepts_qt6_dir_pointing_at_the_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_system_qt: None
) -> None:
    cmake_dir = make_qt_tree(tmp_path / "qt", "6.11.1", [])
    monkeypatch.setenv("Qt6_DIR", str(cmake_dir))
    assert find_qt6(None).cmake_dir == cmake_dir


def test_find_qt6_uses_qt_cmake_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_system_qt: None
) -> None:
    cmake_dir = make_qt_tree(tmp_path / "qt", "6.11.1", [])
    qt_cmake = tmp_path / "qt" / "bin" / "qt-cmake"
    monkeypatch.setattr(doctor, "find_qt_cmake", lambda _root: qt_cmake)
    probe = find_qt6(None)
    assert probe.cmake_dir == cmake_dir
    assert probe.origin == str(qt_cmake)


def test_find_qt6_not_found(no_system_qt: None) -> None:
    probe = find_qt6(None)
    assert probe.cmake_dir is None


def test_qt_version_reads_impl_file(tmp_path: Path) -> None:
    cmake_dir = make_qt_tree(tmp_path, "6.11.1", [])
    assert qt_version(cmake_dir) == (6, 11, 1)


def test_qt_version_none_without_version_file(tmp_path: Path) -> None:
    cmake_dir = make_qt_tree(tmp_path, "6.11.1", [])
    (cmake_dir / "Qt6ConfigVersionImpl.cmake").unlink()
    assert qt_version(cmake_dir) is None


def test_missing_qt_components(tmp_path: Path) -> None:
    cmake_dir = make_qt_tree(tmp_path, "6.11.1", ["Core", "Gui"])
    assert missing_qt_components(cmake_dir, ["Core", "Gui", "SerialPort"]) == ["SerialPort"]


def test_missing_qt_components_follows_dependencies(tmp_path: Path) -> None:
    # Fedora's split: LocationPrivate's Config exists but needs CorePrivate.
    cmake_dir = make_qt_tree(tmp_path, "6.11.1", ["Core", "Location", "LocationPrivate"])
    (cmake_dir.parent / "Qt6LocationPrivate" / "Qt6LocationPrivateDependencies.cmake").write_text(
        "set(Qt6LocationPrivate_FIND_DEPENDENCIES_REQUIRED TRUE)\n"
        'list(APPEND _third_party_deps "Qt6CorePrivate\\;FALSE\\;6.11.1")\n'
        'list(APPEND _third_party_deps "Qt6Location\\;FALSE\\;6.11.1")\n',
        encoding="utf-8",
    )
    missing = missing_qt_components(cmake_dir, ["Core", "LocationPrivate"])
    assert missing == ["CorePrivate (via LocationPrivate)"]


def test_qt_version_range_from_build_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CONFIG_FILE", raising=False)
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "build-config.json").write_text(
        json.dumps({"qt": {"version": "6.11.1", "minimum_version": "6.11.0"}}), encoding="utf-8"
    )
    (tmp_path / "CMakeLists.txt").write_text("", encoding="utf-8")
    assert qt_version_range(tmp_path) == ((6, 11, 0), (6, 11, 1))


def test_qt_version_range_custom_overrides_win(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CONFIG_FILE", raising=False)
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "build-config.json").write_text(
        json.dumps({"qt": {"version": "6.11.1", "minimum_version": "6.11.0"}}), encoding="utf-8"
    )
    (tmp_path / "CMakeLists.txt").write_text("", encoding="utf-8")
    overrides = tmp_path / "custom" / "cmake" / "CustomOverrides.cmake"
    overrides.parent.mkdir(parents=True)
    overrides.write_text(
        'set(QGC_QT_MAXIMUM_VERSION "6.12.0" CACHE STRING "Maximum Supported Qt Version" FORCE)\n',
        encoding="utf-8",
    )
    assert qt_version_range(tmp_path) == ((6, 11, 0), (6, 12, 0))


def test_qt_install_hint_prefers_the_distro_packages_on_fedora(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(install_deps_common, "detect_platform", lambda: "fedora")
    assert qt_install_hint(REPO_ROOT).startswith("just install-deps --category qt")


def test_qt_install_hint_runs_from_the_tools_venv_when_uv_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(install_deps_common, "detect_platform", lambda: "debian")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else None)
    hint = qt_install_hint(REPO_ROOT)
    assert hint.startswith("uv run --project tools --extra qt python3 tools/setup/install_qt.py")
    assert "--outdir ~/Qt" in hint


def test_qt_install_hint_falls_back_to_pipx_without_uv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(install_deps_common, "detect_platform", lambda: "debian")
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    hint = qt_install_hint(REPO_ROOT)
    assert hint.startswith("pipx install aqtinstall, then python3 tools/setup/install_qt.py")


# -- WSLg --------------------------------------------------------------------


def test_wslg_gpu_status_none_off_wsl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "_WSL_GPU_DEVICE", tmp_path / "dxg")
    assert wslg_gpu_status() is None


def test_wslg_gpu_status_reports_the_driver_without_gating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "dxg").write_text("", encoding="utf-8")
    monkeypatch.setattr(doctor, "_WSL_GPU_DEVICE", tmp_path / "dxg")
    monkeypatch.delenv("GALLIUM_DRIVER", raising=False)
    ok, detail = wslg_gpu_status() or (None, "")
    assert ok is True and "llvmpipe" in detail and "WSL_GPU=1" in detail
    monkeypatch.setenv("GALLIUM_DRIVER", "d3d12")
    ok, detail = wslg_gpu_status() or (None, "")
    assert ok is True and detail.startswith("GALLIUM_DRIVER=d3d12")


def test_serial_group_status_reads_session_groups(monkeypatch: pytest.MonkeyPatch) -> None:
    import grp

    entry = grp.struct_group(("dialout", "x", 18, ["someone"]))
    monkeypatch.setattr(doctor, "current_platform", lambda: "linux")
    monkeypatch.setattr(
        grp,
        "getgrnam",
        lambda name: entry if name == "dialout" else (_ for _ in ()).throw(KeyError(name)),
    )
    monkeypatch.setattr(os, "getgroups", lambda: [18, 1000])
    assert serial_group_status() == (True, "dialout")
    monkeypatch.setattr(os, "getgroups", lambda: [1000])
    monkeypatch.setenv("USER", "someone")
    ok, detail = serial_group_status() or (None, "")
    assert ok is True and "new session" in detail
    monkeypatch.setenv("USER", "nobody")
    ok, detail = serial_group_status() or (None, "")
    assert ok is False and "usermod -aG dialout" in detail


def test_wsl_checks_are_none_off_wsl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "_WSL_GPU_DEVICE", tmp_path / "dxg")
    assert wsl_interop_status() is None
    assert wsl_usb_serial_status() is None


def test_wsl_interop_status_reports_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "dxg").write_text("", encoding="utf-8")
    monkeypatch.setattr(doctor, "_WSL_GPU_DEVICE", tmp_path / "dxg")
    monkeypatch.setattr(doctor, "_WSL_INTEROP", tmp_path / "WSLInterop")
    ok, detail = wsl_interop_status() or (None, "")
    assert ok is False and "binfmt.d" in detail
    (tmp_path / "WSLInterop").write_text("", encoding="utf-8")
    assert wsl_interop_status() == (True, "registered")


# -- build directory ---------------------------------------------------------


def test_build_cache_values_parses_typed_lines(tmp_path: Path) -> None:
    cache = tmp_path / "CMakeCache.txt"
    cache.write_text(
        "# comment\n"
        "// help text\n"
        "CMAKE_BUILD_TYPE:STRING=Release\n"
        "Qt6_DIR:PATH=/usr/lib64/cmake/Qt6\n"
        "BUILD_TESTING:INTERNAL=OFF\n"
        "no-equals-line\n"
        "\n",
        encoding="utf-8",
    )
    assert build_cache_values(cache) == {
        "CMAKE_BUILD_TYPE": "Release",
        "Qt6_DIR": "/usr/lib64/cmake/Qt6",
        "BUILD_TESTING": "OFF",
    }


# -- main --------------------------------------------------------------------


def test_main_lint_blocked_without_tools(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert main(["--target", "lint"]) == 1
    captured = capsys.readouterr()
    assert "blocked: just lint" in captured.err
    assert "ready:" not in captured.out


def test_main_footer_names_install_deps_only_for_packaged_failures(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Everything missing: the host tools are package-manager work.
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert main(["--target", "lint"]) == 1
    assert "just install-deps" in capsys.readouterr().err

    # Only pre-commit and the compile database missing: neither is a package.
    monkeypatch.setattr(
        shutil, "which", lambda name: None if name == "pre-commit" else f"/usr/bin/{name}"
    )
    monkeypatch.setattr(doctor, "probe_version", lambda *_a, **_k: (99, 0, 0))
    assert main(["--target", "lint"]) == 1
    err = capsys.readouterr().err
    assert "just install-deps" not in err
    assert "names its fix" in err


def test_main_test_target_ready_on_a_complete_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    required = qt_required_components(REPO_ROOT / "CMakeLists.txt")
    cmake_dir = make_qt_tree(tmp_path / "qt", "6.11.1", [*required, "Test"])
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "CMakeCache.txt").write_text(
        "CMAKE_GENERATOR:INTERNAL=Ninja\n"
        "CMAKE_BUILD_TYPE:STRING=Debug\n"
        "QGC_APP_NAME:STRING=QGroundControl\n"
        f"Qt6_DIR:PATH={cmake_dir}\n"
        "BUILD_TESTING:INTERNAL=ON\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(doctor, "probe_version", lambda *_a, **_k: (99, 0, 0))
    monkeypatch.setattr(doctor, "gstreamer_status", lambda _minimum: (True, "1.28.4"))
    monkeypatch.setattr(doctor, "qt_version_range", lambda _root: ((6, 11, 0), (6, 12, 0)))
    monkeypatch.setenv("DISPLAY", ":0")

    rc = main(["--target", "test", "--qt-root", str(tmp_path / "qt"), "-B", str(build_dir)])

    captured = capsys.readouterr()
    assert rc == 0, captured.out + captured.err
    assert "ready: just configure / just build" in captured.out
    assert "ready: just test" in captured.out
    assert "Next: just test" in captured.out
    assert captured.err == ""


def test_main_reads_a_failed_configure_as_no_qt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "CMakeCache.txt").write_text(
        "CMAKE_GENERATOR:INTERNAL=Ninja\n"
        "CMAKE_BUILD_TYPE:STRING=Release\n"
        "Qt6_DIR:PATH=Qt6_DIR-NOTFOUND\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(doctor, "find_qt6", lambda _root: QtProbe())
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    main(["--target", "build", "-B", str(build_dir), "-t", "Release"])
    out = capsys.readouterr().out
    assert "last configure found no Qt" in out
    assert "NOTFOUND, which no longer exists" not in out


def test_main_warns_when_cached_qt_vanished(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "CMakeCache.txt").write_text(
        "CMAKE_GENERATOR:INTERNAL=Ninja\n"
        "CMAKE_BUILD_TYPE:STRING=Release\n"
        f"Qt6_DIR:PATH={tmp_path / 'gone' / 'lib' / 'cmake' / 'Qt6'}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(doctor, "find_qt6", lambda _root: QtProbe())
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    assert main(["--target", "build", "-B", str(build_dir), "-t", "Release"]) == 1
    out = capsys.readouterr().out
    assert "no longer exists" in out
