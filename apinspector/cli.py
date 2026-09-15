"""Argument parsing and entry-point orchestration."""

from __future__ import annotations

import argparse
import json
import os
import sys

from .adb import AdbClient, AdbError
from .exporters import write_recommendations, write_report_json
from .paths import BLOATWARE_PATH, default_adb_path
from .report import render_cli
from .scanning import scan
from .scoring import empty_scan, load_bloatware
from .web.server import serve


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Android Package Inspector")
    parser.add_argument("--all", action="store_true",
                        help="include system apps (default: user apps only)")
    parser.add_argument("--cli", action="store_true",
                        help="headless console report + JSON/TXT export")
    parser.add_argument("--serial", help="device serial (if multiple connected)")
    parser.add_argument("--adb", default=default_adb_path(), help="path to adb binary")
    parser.add_argument("--port", type=int, default=8765, help="web UI port")
    parser.add_argument("--no-open", action="store_true", help="don't open the browser")
    parser.add_argument("--dry-run", action="store_true",
                        help="log actions but never execute freeze/uninstall on the device")
    parser.add_argument("--report", help="load existing report.json (runs in offline mode without phone)")
    parser.add_argument("--out-dir", default=os.getcwd(), help="output directory")
    parser.add_argument("--no-color", action="store_true")
    return parser


def _load_report(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    data["offline"] = True
    return data


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    load_bloatware(BLOATWARE_PATH)
    color = sys.stdout.isatty() and not args.no_color

    # Explicit offline mode via --report
    if args.report:
        if not os.path.exists(args.report):
            print(f"error: report file not found: '{args.report}'", file=sys.stderr)
            return 2
        try:
            data = _load_report(args.report)
        except Exception as exc:
            print(f"error: no se pudo leer '{args.report}': {exc}", file=sys.stderr)
            return 2
        print(f"Modo offline: cargados {len(data.get('apps', []))} paquetes desde '{args.report}'.", file=sys.stderr)
        if args.cli:
            render_cli(data, color)
            return 0
        serve(None, data, args.out_dir, args.port, args.all, not args.no_open,
              dry_run=True, offline=True)
        return 0

    adb = AdbClient(args.adb, serial=args.serial)
    try:
        adb.resolve_serial()
    except AdbError as exc:
        if args.cli:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"Aviso: {exc}", file=sys.stderr)
        print("Iniciando la UI sin dispositivo. Usa el boton WiFi para conectar "
              "por ADB inalambrico (IP o pairing Android 11+).", file=sys.stderr)
        serve(adb, empty_scan(), args.out_dir, args.port, args.all,
              not args.no_open, dry_run=args.dry_run, no_device=True)
        return 0

    def progress(i, total, pkg):
        print(f"\r  scanning {i}/{total}  {pkg[:40]:<40}", end="", file=sys.stderr)

    print(f"Scanning device {adb.serial} "
          f"({'all apps' if args.all else 'user apps'})...", file=sys.stderr)
    data = scan(adb, args.all, progress=progress)
    print(file=sys.stderr)

    if args.cli:
        render_cli(data, color)
        jp = write_report_json(data, args.out_dir)
        tp = write_recommendations(data, args.out_dir)
        print(f"\n  report.json          -> {jp}")
        print(f"  recommendations.txt  -> {tp}")
        return 0

    if args.dry_run:
        print("  [dry-run] destructive actions will be logged, not executed.",
              file=sys.stderr)
    serve(adb, data, args.out_dir, args.port, args.all, not args.no_open,
          dry_run=args.dry_run)
    return 0
