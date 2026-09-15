"""Filesystem locations used across the package.

The project is meant to be run in place (no installation), so paths are resolved
from this file's location. ``bloatware.json`` is user-editable data and stays at
the project root; static UI assets live next to the web server module.
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
BLOATWARE_PATH = PROJECT_ROOT / "bloatware.json"
STATIC_DIR = PACKAGE_DIR / "web" / "static"


def default_adb_path() -> str:
    """Resolve the adb binary: current dir, project root, then PATH."""
    candidates = (
        os.path.join(os.getcwd(), "adb.exe"),
        os.path.join(os.getcwd(), "adb"),
        str(PROJECT_ROOT / "adb.exe"),
        str(PROJECT_ROOT / "adb"),
    )
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return "adb"
