"""Report exporters: report.json and recommendations.txt."""

from __future__ import annotations

import json
import os


def write_report_json(data: dict, out_dir: str) -> str:
    path = os.path.join(out_dir, "report.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return path


def write_recommendations(data: dict, out_dir: str, min_stars: int = 4) -> str:
    path = os.path.join(out_dir, "recommendations.txt")
    lines = ["# Android Package Inspector — recommendations",
             f"# Generated {data['generated_at']} · device {data.get('serial')}",
             "#",
             "# freeze (reversible):  adb shell pm enable <pkg> to undo",
             "# uninstall is per-user and only offered for user apps",
             ""]
    flagged = [a for a in data["apps"]
               if a.get("stars", 0) >= min_stars and not a.get("critical")]
    for app in flagged:
        pkg = app["package"]
        lines.append("=" * 60)
        lines.append(f"{pkg}  [{'★' * app['stars']}{'☆' * (5 - app['stars'])}]  "
                     f"{app['score_pct']}/100  ({app['type']})")
        for r in app.get("reasons", []):
            lines.append(f"  - {r}")
        lines.append("")
        lines.append(f"  adb shell pm disable-user --user 0 {pkg}   # freeze (safe)")
        if app["type"] == "user":
            lines.append(f"  adb shell pm uninstall --user 0 {pkg}     # uninstall (aggressive)")
        lines.append("")
    if not flagged:
        lines.append("No apps crossed the risk threshold. Nothing to recommend.")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return path
