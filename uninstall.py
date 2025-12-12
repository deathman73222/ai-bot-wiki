#!/usr/bin/env python3
"""Cross-platform uninstaller for AI Bot.

This script attempts to remove the installed application folder,
delete desktop/start-menu shortcuts on Windows and optionally uninstall
Python packages listed in the repository's requirements.txt.

Run this with the same Python used to install dependencies when possible.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


def read_install_path_from_config(default: Path) -> Optional[Path]:
    """If a config.json exists in the default location, read install_path."""
    cfg = default / "config.json"
    if not cfg.exists():
        return None

    try:
        with cfg.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        path = data.get("install_path")
        if path:
            return Path(path)
    except (OSError, json.JSONDecodeError):  # pragma: no cover - best-effort only
        # If we cannot read/parse the file, silently ignore and continue
        pass

    return None


def confirm(prompt: str) -> bool:
    resp = input(f"{prompt} [y/N]: ").strip().lower()
    return resp == "y"


def remove_tree(path: Path) -> bool:
    try:
        if path.exists():
            shutil.rmtree(path)
            print(f"Removed: {path}")
            return True
        print(f"Not found (skipping): {path}")
        return False
    except OSError as exc:  # pragma: no cover - I/O errors depend on system
        print(f"Failed to remove {path}: {exc}")
        return False


def remove_windows_shortcuts() -> None:
    # Desktop shortcut
    desktop = Path.home() / "Desktop" / "AI Bot.lnk"
    try:
        if desktop.exists():
            desktop.unlink()
            print(f"Removed desktop shortcut: {desktop}")
    except OSError as exc:
        print(f"Could not remove desktop shortcut: {exc}")

    # Start Menu
    start_menu = Path.home() / "AppData" / "Roaming" / "Microsoft" / \
        "Windows" / "Start Menu" / "Programs" / "AI Bot"
    try:
        if start_menu.exists():
            shutil.rmtree(start_menu)
            print(f"Removed Start Menu entries: {start_menu}")
    except OSError as exc:
        print(f"Could not remove Start Menu entries: {exc}")


def attempt_pip_uninstall(req_file: Path) -> None:
    if not req_file.exists():
        print(
            f"requirements.txt not found at {req_file}; skipping pip uninstall.")
        return

    print("Attempting to uninstall packages from requirements.txt (this may uninstall packages globally).")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "uninstall", "-r", str(req_file), "-y"])
        print("Pip uninstall completed.")
    except subprocess.CalledProcessError as exc:
        print(
            f"Pip uninstall failed or some packages could not be removed: {exc}")


def main() -> int:
    default_install = Path.home() / "AI Bot"
    inferred = read_install_path_from_config(default_install)
    if inferred:
        print(f"Found configuration indicating installation at: {inferred}")
    install_path = inferred or default_install

    print("AI Bot Uninstaller")
    print("===================")
    print(f"Default installation path: {install_path}")

    user_path = input(
        f"Enter installation path to remove (leave empty to use '{install_path}'): ").strip()
    if user_path:
        install_path = Path(user_path).expanduser()

    if not install_path.exists():
        print(f"Installation path does not exist: {install_path}")
        print("Nothing to do.")
        return 0

    print("WARNING: This will permanently delete the installation directory and its contents.")
    if not confirm(f"Continue and remove {install_path}?"):
        print("Aborted by user.")
        return 0

    # Attempt to remove the installation directory
    ok = remove_tree(install_path)

    # Remove Windows-specific shortcuts if on Windows
    if sys.platform.startswith("win"):
        remove_windows_shortcuts()

    # Offer to remove pip packages
    req_file = Path(__file__).parent / "requirements.txt"
    if confirm("Attempt to uninstall Python packages listed in requirements.txt? This may affect your system Python."):
        attempt_pip_uninstall(req_file)

    print("Uninstallation finished. If some files remained (in use), try again after closing running applications or rebooting.")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
