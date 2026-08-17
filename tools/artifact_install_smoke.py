from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import onnxruntime  # noqa: F401  # load DLLs before PySide6 on Windows
from PySide6 import QtCore
from PySide6 import QtWidgets

import labelme
from labelme import __appname__
from labelme import __version__
from labelme._app import MainWindow


def _check_source_isolation(*, source_root: Path) -> None:
    source_entries = [
        entry for entry in sys.path if Path(entry).resolve().is_relative_to(source_root)
    ]
    if source_entries:
        raise RuntimeError(f"source checkout is on sys.path: {source_entries}")

    package_path = Path(labelme.__file__).resolve()
    if package_path.is_relative_to(source_root):
        raise RuntimeError(f"labelme imported from source checkout: {package_path}")


def _check_packaged_resources() -> None:
    # Packaging mistakes drop whole directories, so one file per resource kind
    # is enough to prove the artifact carried config, icons, and translations.
    package_dir = Path(labelme.__file__).resolve().parent
    missing_resources = [
        relative_path
        for relative_path in (
            "_config/default_config.yaml",
            "icons/icon-256.png",
            "translate/ja_JP.qm",
        )
        if not (package_dir / relative_path).is_file()
    ]
    if missing_resources:
        raise RuntimeError(f"packaged resources are missing: {missing_resources}")


def _check_cli() -> None:
    executable = shutil.which("labelme")
    if executable is None:
        raise RuntimeError("labelme console script is not installed")

    help_output = subprocess.run(
        [executable, "--help"], capture_output=True, check=True, text=True
    ).stdout
    if "usage: labelme" not in help_output:
        raise RuntimeError("labelme --help did not print its usage")

    version_output = subprocess.run(
        [executable, "--version"], capture_output=True, check=True, text=True
    ).stdout.strip()
    expected_version = f"{__appname__} {__version__}"
    if version_output != expected_version:
        raise RuntimeError(
            f"labelme --version printed {version_output!r}, "
            f"expected {expected_version!r}"
        )


def _start_application() -> None:
    app = QtWidgets.QApplication([])
    # Constructing the window loads the default config, icons, and dock layout
    # from the installed package, which is the startup coverage this smoke
    # test is after.
    window = MainWindow(
        config_file=None,
        config_overrides={},
        file_or_dir=None,
        output_dir=None,
    )
    window.show()
    app.processEvents()
    if not window.isVisible():
        raise RuntimeError("the application window did not start")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    args = parser.parse_args()

    _check_source_isolation(source_root=args.source_root.resolve())
    _check_packaged_resources()

    with tempfile.TemporaryDirectory() as home_dir:
        # Keep the run from touching the invoking user's real home: the CLI
        # writes a log file under it, and the window writes QSettings (which
        # go to the registry on Windows unless forced to ini files).
        os.environ["HOME"] = home_dir
        os.environ["USERPROFILE"] = home_dir
        os.environ["LOCALAPPDATA"] = home_dir
        QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
        QtCore.QSettings.setPath(
            QtCore.QSettings.Format.IniFormat,
            QtCore.QSettings.Scope.UserScope,
            home_dir,
        )
        _check_cli()
        _start_application()


if __name__ == "__main__":
    main()
