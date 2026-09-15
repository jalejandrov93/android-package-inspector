"""Per-package `dumpsys package` parsing."""

from __future__ import annotations

import re

from .config import DANGEROUS_PERMS, INSTALLER_LABELS, SYSTEM_PATH_PREFIXES


def _section(text: str, header: str, next_headers: tuple[str, ...]) -> str:
    """Return the block of lines under `header` up to the next known header."""
    start = text.find(header)
    if start == -1:
        return ""
    start += len(header)
    end = len(text)
    for nh in next_headers:
        idx = text.find(nh, start)
        if idx != -1:
            end = min(end, idx)
    return text[start:end]


def parse_package(pkg: str, raw: str) -> dict:
    app: dict = {"package": pkg, "parse_error": False}

    def find(pattern, default=None, flags=0):
        m = re.search(pattern, raw, flags)
        return m.group(1).strip() if m else default

    app["code_path"] = find(r"^\s*codePath=(.+)$", flags=re.MULTILINE)
    app["version_name"] = find(r"^\s*versionName=(.+)$", flags=re.MULTILINE)
    vc = find(r"versionCode=(\d+)")
    app["version_code"] = int(vc) if vc else None
    uid = find(r"^\s*userId=(\d+)$", flags=re.MULTILINE)
    app["uid"] = int(uid) if uid else None
    app["first_install_time"] = find(r"firstInstallTime=(.+)")
    app["last_update_time"] = find(r"lastUpdateTime=(.+)")

    installer = find(r"installerPackageName=(.+)")
    app["installer"] = installer
    app["installer_label"] = INSTALLER_LABELS.get(installer, installer or "Unknown")

    sig = find(r"signatures=PackageSignatures\{[^,]+,\s*signatures:\[([^\]]*)\]")
    app["signature"] = sig

    flags = find(r"^\s*flags=\[(.*?)\]", flags=re.MULTILINE) or ""
    app["flags"] = flags.split()
    code_path = app.get("code_path") or ""
    is_system = "SYSTEM" in flags or code_path.startswith(SYSTEM_PATH_PREFIXES)
    app["type"] = "system" if is_system else "user"

    # Permissions: collect every "<perm>: granted=true" across install/runtime.
    granted = set(re.findall(r"([a-zA-Z0-9_.]+):\s*granted=true", raw))
    app["granted_permissions"] = sorted(granted)
    app["dangerous_permissions"] = sorted(granted & DANGEROUS_PERMS)

    def has_perm(name: str) -> bool:
        return f"android.permission.{name}" in granted or \
            re.search(rf"android\.permission\.{name}\b", raw) is not None

    app["internet"] = has_perm("INTERNET")
    app["foreground_service"] = has_perm("FOREGROUND_SERVICE")
    app["overlay"] = "android.permission.SYSTEM_ALERT_WINDOW" in raw
    app["auto_start"] = has_perm("RECEIVE_BOOT_COMPLETED")

    # Resolver tables: components with intent filters (effectively exported).
    activity_tbl = _section(raw, "Activity Resolver Table:",
                            ("Receiver Resolver Table:", "Service Resolver Table:",
                             "Provider Resolver Table:", "Key Set Manager:", "Packages:"))
    receiver_tbl = _section(raw, "Receiver Resolver Table:",
                            ("Service Resolver Table:", "Provider Resolver Table:",
                             "Key Set Manager:", "Packages:"))
    service_tbl = _section(raw, "Service Resolver Table:",
                            ("Provider Resolver Table:", "Key Set Manager:", "Packages:"))
    provider_tbl = _section(raw, "Provider Resolver Table:",
                            ("Key Set Manager:", "Packages:"))

    def count_components(tbl: str) -> int:
        return len(set(re.findall(rf"{re.escape(pkg)}/([a-zA-Z0-9_.$]+)", tbl)))

    app["exported_activities"] = count_components(activity_tbl)
    app["exported_receivers"] = count_components(receiver_tbl)
    app["exported_services"] = count_components(service_tbl)
    app["exported_providers"] = count_components(provider_tbl)
    app["exports_services"] = app["exported_services"] > 0

    app["boot_completed"] = 'android.intent.action.BOOT_COMPLETED"' in receiver_tbl
    app["is_launcher"] = 'android.intent.category.HOME"' in activity_tbl

    app["accessibility"] = "android.permission.BIND_ACCESSIBILITY_SERVICE" in raw
    app["device_admin"] = "android.permission.BIND_DEVICE_ADMIN" in raw
    return app
