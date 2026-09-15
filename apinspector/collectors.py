"""Global device collectors: one adb call each, shared by all packages."""

from __future__ import annotations

import re

from .adb import AdbClient


def collect_overlay_pkgs(adb: AdbClient) -> set[str]:
    out = adb.shell("cmd appops query-op SYSTEM_ALERT_WINDOW allow")
    return {ln.strip() for ln in out.splitlines() if ln.strip() and "." in ln}


def collect_accessibility(adb: AdbClient) -> set[str]:
    out = adb.shell("settings get secure enabled_accessibility_services").strip()
    if not out or out == "null":
        return set()
    pkgs = set()
    for component in out.split(":"):
        component = component.strip()
        if "/" in component:
            pkgs.add(component.split("/", 1)[0])
    return pkgs


def collect_device_admins(adb: AdbClient) -> set[str]:
    out = adb.shell("dumpsys device_policy")
    pkgs = set()
    for match in re.finditer(r"([a-zA-Z0-9_.]+)/[a-zA-Z0-9_.$]+", out):
        pkgs.add(match.group(1))
    # Filter to plausible package names (must contain a dot).
    return {p for p in pkgs if "." in p}


def collect_default_launcher(adb: AdbClient) -> str | None:
    out = adb.shell("cmd shortcut get-default-launcher")
    m = re.search(r"ComponentInfo\{([^/]+)/", out)
    return m.group(1) if m else None


def collect_frozen_pkgs(adb: AdbClient) -> set[str]:
    """Packages currently disabled/frozen for user 0 (pm list packages -d)."""
    out = adb.shell("pm list packages -d")
    return {ln.replace("package:", "").strip() for ln in out.splitlines() if ln.strip()}
