"""Criticality, risk scoring, bloatware tagging and report packing."""

from __future__ import annotations

import json

from .config import CRITICAL_PACKAGES, CRITICAL_KEYWORDS, MAX_RAW, WEIGHTS
from .util import now_iso

# Populated by load_bloatware(); empty dict disables bloatware tagging.
BLOATWARE: dict = {}


def load_bloatware(path) -> None:
    """Load a known-bloatware list from a JSON file.

    Shape: {"<pkg>": {"category": str, "removal": str, "description": str}}.
    Accepts either the raw mapping or one wrapped under a "packages" key.
    A missing file is fine — bloatware tagging is simply disabled.
    """
    global BLOATWARE
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        BLOATWARE = data.get("packages", data) if isinstance(data, dict) else {}
    except (OSError, ValueError):
        BLOATWARE = {}


def annotate_bloatware(app: dict) -> None:
    app["bloatware"] = BLOATWARE.get(app["package"])


def classify_criticality(app: dict) -> None:
    pkg = app["package"].lower()
    if app["package"] in CRITICAL_PACKAGES:
        app["critical"] = True
        app["critical_reason"] = CRITICAL_PACKAGES[app["package"]]
        return
    for kw in CRITICAL_KEYWORDS:
        if kw in pkg:
            app["critical"] = True
            app["critical_reason"] = f"Possible finance/banking app (matched '{kw}')"
            return
    app["critical"] = False
    app["critical_reason"] = None


def score_risk(app: dict) -> None:
    raw = 0
    reasons: list[str] = []
    is_user = app["type"] == "user"

    if app["overlay"]:
        raw += WEIGHTS["overlay"]
        reasons.append("Puede dibujar sobre otras apps (overlay)")
    if app["accessibility"]:
        raw += WEIGHTS["accessibility"]
        reasons.append("Usa servicios de accesibilidad")
    if app["boot_completed"]:
        raw += WEIGHTS["boot_completed"]
        reasons.append("Arranca al iniciar el dispositivo")
    if app["foreground_service"]:
        raw += WEIGHTS["foreground_service"]
        reasons.append("Ejecuta servicios en primer plano")
    if app["internet"]:
        raw += WEIGHTS["internet"]
        reasons.append("Tiene acceso a internet")
    unknown_installer = app["installer_label"] == "Unknown"
    if unknown_installer:
        raw += WEIGHTS["unknown_installer"]
        reasons.append("Installer desconocido")
    if app["exports_services"]:
        raw += WEIGHTS["exports_services"]
        reasons.append("Exporta servicios")
    if is_user:
        raw += WEIGHTS["user_app"]
    # Untrusted-signature heuristic: user app installed from an unknown source.
    if is_user and unknown_installer:
        raw += WEIGHTS["untrusted_signature"]
        reasons.append("Firma no verificada (usuario + origen desconocido)")

    if app["type"] == "system" and raw <= WEIGHTS["internet"] + WEIGHTS["foreground_service"]:
        reasons = ["Componente de sistema"]

    pct = round(raw / MAX_RAW * 100)
    if pct >= 70:
        stars = 5
    elif pct >= 50:
        stars = 4
    elif pct >= 33:
        stars = 3
    elif pct >= 18:
        stars = 2
    else:
        stars = 1
    app["score_raw"] = raw
    app["score_pct"] = pct
    app["stars"] = stars
    app["reasons"] = reasons


def finalize_app(app, pkg, overlay, a11y, admins, launcher, frozen):
    app["overlay"] = app.get("overlay", False) or pkg in overlay
    app["accessibility"] = app.get("accessibility", False)
    app["accessibility_active"] = pkg in a11y
    app["device_admin_active"] = pkg in admins
    app["is_launcher"] = app.get("is_launcher", False) or pkg == launcher
    app["frozen"] = pkg in frozen
    app.setdefault("type", "user")
    classify_criticality(app)
    annotate_bloatware(app)
    if not app.get("parse_error"):
        score_risk(app)
    else:
        app.update(score_raw=0, score_pct=0, stars=1, critical=False,
                   critical_reason=None, dangerous_permissions=[])


def pack_scan(apps, serial, launcher):
    return {
        "generated_at": now_iso(),
        "serial": serial,
        "default_launcher": launcher,
        "counts": {
            "total": len(apps),
            "user": sum(1 for a in apps if a["type"] == "user"),
            "system": sum(1 for a in apps if a["type"] == "system"),
            "high_risk": sum(1 for a in apps if a.get("stars", 0) >= 4),
            "critical": sum(1 for a in apps if a.get("critical")),
            "bloatware": sum(1 for a in apps if a.get("bloatware")),
        },
        "apps": apps,
    }


def empty_scan() -> dict:
    """Placeholder dataset for the UI when no device is connected yet."""
    return {
        "generated_at": now_iso(),
        "serial": None,
        "default_launcher": None,
        "no_device": True,
        "counts": {"total": 0, "user": 0, "system": 0,
                   "high_risk": 0, "critical": 0, "bloatware": 0},
        "apps": [],
    }
