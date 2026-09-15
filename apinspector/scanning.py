"""Scan orchestration: package listing, batch scan and streaming scan."""

from __future__ import annotations

from .adb import AdbClient
from .collectors import (
    collect_accessibility,
    collect_default_launcher,
    collect_device_admins,
    collect_frozen_pkgs,
    collect_overlay_pkgs,
)
from .parsing import parse_package
from .scoring import finalize_app, pack_scan


def list_packages(adb: AdbClient, include_system: bool) -> list[str]:
    flag = "" if include_system else "-3"
    out = adb.shell(f"pm list packages {flag}".strip())
    return sorted(
        ln.replace("package:", "").strip()
        for ln in out.splitlines() if ln.strip()
    )


def _collect_globals(adb: AdbClient) -> dict:
    return {
        "overlay": collect_overlay_pkgs(adb),
        "a11y": collect_accessibility(adb),
        "admins": collect_device_admins(adb),
        "launcher": collect_default_launcher(adb),
        "frozen": collect_frozen_pkgs(adb),
    }


def _parse_one(adb: AdbClient, pkg: str) -> dict:
    try:
        raw = adb.shell(f"dumpsys package {pkg}")
        return parse_package(pkg, raw)
    except Exception:  # noqa: BLE001 - one bad package must not abort the scan
        return {"package": pkg, "parse_error": True, "type": "user",
                "reasons": ["No se pudo leer el paquete"]}


def scan(adb: AdbClient, include_system: bool, progress=None) -> dict:
    g = _collect_globals(adb)
    packages = list_packages(adb, include_system)
    apps = []
    total = len(packages)
    for i, pkg in enumerate(packages, 1):
        if progress:
            progress(i, total, pkg)
        app = _parse_one(adb, pkg)
        finalize_app(app, pkg, g["overlay"], g["a11y"], g["admins"],
                     g["launcher"], g["frozen"])
        apps.append(app)

    apps.sort(key=lambda a: a.get("score_pct", 0), reverse=True)
    return pack_scan(apps, adb.serial, g["launcher"])


def scan_stream(adb: AdbClient, include_system: bool):
    """Generator variant: yields {type:'progress'|'done'} for live UI feedback."""
    g = _collect_globals(adb)
    packages = list_packages(adb, include_system)
    total = len(packages)
    apps = []
    for i, pkg in enumerate(packages, 1):
        yield {"type": "progress", "i": i, "n": total, "package": pkg}
        app = _parse_one(adb, pkg)
        finalize_app(app, pkg, g["overlay"], g["a11y"], g["admins"],
                     g["launcher"], g["frozen"])
        apps.append(app)
    apps.sort(key=lambda a: a.get("score_pct", 0), reverse=True)
    yield {"type": "done", "data": pack_scan(apps, adb.serial, g["launcher"])}
