"""Destructive actions with backend-enforced safety gates."""

from __future__ import annotations

import os

from .adb import AdbClient
from .config import ACTION_TEMPLATES
from .util import now_iso


def check_action_gate(action: str, packages: list[str], app_index: dict,
                      confirm: bool) -> dict | None:
    """Backend safety gate. Returns an error dict to abort, or None to proceed."""
    if action not in ACTION_TEMPLATES:
        return {"error": f"unknown action '{action}'", "status": 400}
    critical_hits = []
    for pkg in packages:
        app = app_index.get(pkg, {})
        if action == "uninstall" and app.get("type") == "system":
            return {"status": 403,
                    "error": f"'{pkg}' is a system app; uninstall is blocked. "
                             f"Use freeze instead."}
        if action in ("uninstall", "freeze") and app.get("critical"):
            critical_hits.append({"package": pkg, "reason": app.get("critical_reason")})
    if critical_hits and not confirm:
        return {
            "status": 409,
            "needs_confirm": True,
            "critical": critical_hits,
            "commands": [ACTION_TEMPLATES[action].format(pkg=p) for p in packages],
        }
    return None


def _run_one(adb: AdbClient, action: str, pkg: str, out_dir: str,
             dry_run: bool) -> dict:
    command = ACTION_TEMPLATES[action].format(pkg=pkg)
    if dry_run:
        log_action(out_dir, command, True, "[dry-run]")
        return {"package": pkg, "command": command, "ok": True,
                "output": "[dry-run] not executed"}
    out = adb.shell(command).strip()
    ok = "Success" in out
    if action == "freeze" and "disabled" in out.lower():
        ok = True
    if action == "unfreeze" and ("enabled" in out.lower() or "Success" in out):
        ok = True
    log_action(out_dir, command, ok, out)
    return {"package": pkg, "command": command, "ok": ok, "output": out}


def apply_action_stream(adb: AdbClient, action: str, packages: list[str],
                        app_index: dict, confirm: bool, out_dir: str,
                        dry_run: bool = False):
    """Generator: yields a 'gate' event (abort) or start/progress/done events."""
    gate = check_action_gate(action, packages, app_index, confirm)
    if gate is not None:
        yield {"type": "gate", **gate}
        return
    n = len(packages)
    yield {"type": "start", "total": n, "action": action}
    ok_count = 0
    for i, pkg in enumerate(packages, 1):
        res = _run_one(adb, action, pkg, out_dir, dry_run)
        ok_count += 1 if res["ok"] else 0
        yield {"type": "progress", "i": i, "n": n, **res}
    yield {"type": "done", "ok": ok_count, "total": n, "action": action}


def apply_action(adb: AdbClient, action: str, packages: list[str],
                 app_index: dict, confirm: bool, out_dir: str,
                 dry_run: bool = False) -> dict:
    """Non-streaming wrapper (CLI / tests)."""
    events = list(apply_action_stream(adb, action, packages, app_index,
                                      confirm, out_dir, dry_run))
    for evt in events:
        if evt.get("type") == "gate":
            return {k: v for k, v in evt.items() if k != "type"}
    results = [{k: v for k, v in e.items() if k not in ("type", "i", "n")}
               for e in events if e.get("type") == "progress"]
    return {"status": 200, "results": results}


def log_action(out_dir: str, command: str, ok: bool, output: str) -> None:
    path = os.path.join(out_dir, "actions.log")
    line = f"{now_iso()}\t{'OK ' if ok else 'ERR'}\tadb shell {command}\t{output!r}\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)
