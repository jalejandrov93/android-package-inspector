"""Local HTTP API and static UI server."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

from ..adb import AdbClient, AdbError
from ..actions import apply_action_stream
from ..collectors import collect_frozen_pkgs
from ..exporters import write_report_json, write_recommendations
from ..icons import get_app_icon
from ..paths import STATIC_DIR
from ..scanning import list_packages, scan_stream
from ..wifi import wifi_connect, wifi_pair

_STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}
_CACHEABLE = {".css", ".js", ".svg", ".png", ".ico"}


def load_index() -> bytes:
    """Read the SPA shell from the static directory (cached by the server)."""
    try:
        return (STATIC_DIR / "index.html").read_bytes()
    except OSError as exc:
        return f"<h1>UI not found</h1><p>{exc}</p>".encode("utf-8")


def build_state(adb: AdbClient | None, data: dict, out_dir: str,
                include_system: bool, offline: bool = False,
                no_device: bool = False) -> dict:
    return {
        "adb": adb,
        "data": data,
        "index": {a["package"]: a for a in data["apps"]},
        "out_dir": out_dir,
        "include_system": include_system,
        "offline": offline,
        "no_device": no_device,
    }


def make_handler(state: dict, include_system: bool, dry_run: bool = False):
    index_body = load_index()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence default logging
            pass

        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj: dict):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _open_stream(self):
            # HTTP/1.0 (default) closes the connection after the response, so the
            # client's fetch() reader ends on EOF — no chunked encoding needed.
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

        def _emit(self, evt: dict):
            self.wfile.write((json.dumps(evt, ensure_ascii=False) + "\n").encode("utf-8"))
            self.wfile.flush()

        def _serve_static(self, name: str):
            """Serve a whitelisted asset confined to STATIC_DIR (no traversal)."""
            suffix = os.path.splitext(name)[1].lower()
            target = (STATIC_DIR / name).resolve()
            try:
                target.relative_to(STATIC_DIR.resolve())
            except ValueError:
                self._json(404, {"error": "not found"}); return
            if suffix not in _STATIC_TYPES or not target.is_file():
                self._json(404, {"error": "not found"}); return
            try:
                body = target.read_bytes()
            except OSError:
                self._json(404, {"error": "not found"}); return
            self.send_response(200)
            self.send_header("Content-Type", _STATIC_TYPES[suffix])
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control",
                             "public, max-age=604800" if suffix in _CACHEABLE else "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._send(200, index_body, "text/html; charset=utf-8")
            elif path.startswith("/static/"):
                self._serve_static(unquote(path[len("/static/"):]))
            elif path == "/api/apps":
                self._json(200, state["data"])
            elif path == "/api/state":
                if state.get("offline") or not state.get("adb"):
                    frozen = [a["package"] for a in state["data"]["apps"] if a.get("frozen")]
                    installed = [a["package"] for a in state["data"]["apps"]]
                    self._json(200, {"frozen": sorted(frozen), "installed": sorted(installed)})
                else:
                    # Fast post-action refresh: no full re-scan, just live states.
                    try:
                        frozen = collect_frozen_pkgs(state["adb"])
                        installed = set(list_packages(state["adb"], state["include_system"]))
                    except AdbError:
                        # No reachable device (e.g. WiFi not connected yet): serve cache.
                        frozen = {a["package"] for a in state["data"]["apps"] if a.get("frozen")}
                        installed = {a["package"] for a in state["data"]["apps"]}
                    self._json(200, {"frozen": sorted(frozen),
                                     "installed": sorted(installed)})
            elif path == "/api/device/status":
                self._device_status()
            elif path == "/api/wifi/discover":
                adb = state.get("adb")
                if not adb:
                    self._json(400, {"error": "adb no disponible"}); return
                try:
                    services = adb.mdns_services()
                except AdbError as exc:
                    self._json(500, {"error": str(exc)}); return
                self._json(200, {"ok": True, "services": services})
            elif path.startswith("/api/icon/"):
                pkg = unquote(path[len("/api/icon/"):])
                content, ctype = get_app_icon(pkg, state["out_dir"])
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "public, max-age=604800")
                self.end_headers()
                self.wfile.write(content)
            elif path.startswith("/api/app/"):
                pkg = unquote(path[len("/api/app/"):])
                app = state["index"].get(pkg)
                self._json(200 if app else 404, app or {"error": "not found"})
            elif path == "/api/export":
                jp = write_report_json(state["data"], state["out_dir"])
                tp = write_recommendations(state["data"], state["out_dir"])
                self._json(200, {"report": jp, "recommendations": tp})
            else:
                self._json(404, {"error": "not found"})

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            if not length:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        # ---- wireless ADB ----
        def _activate(self, serial: str | None) -> None:
            adb = state.get("adb")
            if adb and serial:
                adb.serial = serial
                state["no_device"] = False

        def _device_status(self) -> None:
            adb = state.get("adb")
            if not adb:
                self._json(200, {"available": False, "supports_pairing": False,
                                 "devices": [], "adb": None, "serial": None})
                return
            info: dict = {}
            devices: list = []
            try:
                info = adb.version_info()
            except AdbError as exc:
                info = {"error": str(exc)}
            try:
                devices = adb.devices_detail()
            except AdbError as exc:
                info.setdefault("error", str(exc))
            self._json(200, {
                "available": True,
                "supports_pairing": bool(info.get("supports_pairing")),
                "adb": info,
                "devices": devices,
                "serial": adb.serial,
            })

        def _wifi_connect(self) -> None:
            adb = state.get("adb")
            if not adb:
                self._json(400, {"error": "adb no disponible"}); return
            body = self._read_body()
            host = (body.get("host") or "").strip()
            if not host:
                self._json(400, {"error": "falta la IP del dispositivo"}); return
            try:
                port = int(body.get("port") or 5555)
            except (TypeError, ValueError):
                self._json(400, {"error": "puerto invalido"}); return
            res = wifi_connect(adb, host, port)
            self._activate(res.get("serial"))
            self._json(200, res)

        def _wifi_pair(self) -> None:
            adb = state.get("adb")
            if not adb:
                self._json(400, {"error": "adb no disponible"}); return
            try:
                info = adb.version_info()
            except AdbError as exc:
                self._json(500, {"error": str(exc)}); return
            if not info.get("supports_pairing"):
                self._json(400, {"error": "adb demasiado antiguo para pairing; "
                                          "actualiza platform-tools a 30+"})
                return
            body = self._read_body()
            host = (body.get("host") or "").strip()
            code = str(body.get("code") or "").strip()
            try:
                port = int(body.get("pairing_port") or 0)
            except (TypeError, ValueError):
                port = 0
            if not host or not port or not code:
                self._json(400, {"error": "IP, puerto de pairing y codigo son "
                                          "obligatorios"})
                return
            res = wifi_pair(adb, host, port, code)
            self._activate(res.get("serial"))
            self._json(200, res)

        def _wifi_disconnect(self) -> None:
            adb = state.get("adb")
            if not adb:
                self._json(400, {"error": "adb no disponible"}); return
            body = self._read_body()
            host = (body.get("host") or "").strip()
            if not host:
                self._json(400, {"error": "falta la IP"}); return
            try:
                port = int(body.get("port") or 5555)
            except (TypeError, ValueError):
                port = 5555
            try:
                out = adb.disconnect(host, port)
            except AdbError as exc:
                self._json(500, {"error": str(exc)}); return
            self._json(200, {"ok": True, "output": out.strip()})

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/rescan":
                if state.get("offline") or not state.get("adb"):
                    self._json(400, {"error": "Rescan no disponible en modo offline (sin dispositivo conectado)."})
                    return
                body = self._read_body()
                if "system" in body:
                    state["include_system"] = bool(body["system"])
                self._open_stream()
                for evt in scan_stream(state["adb"], state["include_system"]):
                    if evt["type"] == "done":
                        state["data"] = evt["data"]
                        state["index"] = {a["package"]: a for a in evt["data"]["apps"]}
                    self._emit(evt)
            elif path == "/api/action":
                if state.get("offline") or not state.get("adb"):
                    self._json(400, {"error": "Acciones deshabilitadas en modo offline."})
                    return
                body = self._read_body()
                gen = apply_action_stream(
                    state["adb"], body.get("action", ""),
                    body.get("packages", []), state["index"],
                    bool(body.get("confirm")), state["out_dir"], dry_run=dry_run,
                )
                first = next(gen)
                if first.get("type") == "gate":
                    # Safety gate hit before any device change: normal JSON reply.
                    self._json(first.get("status", 400),
                               {k: v for k, v in first.items() if k != "type"})
                    return
                self._open_stream()
                self._emit(first)
                for evt in gen:
                    self._emit(evt)
                # Reflect new frozen state on the server-side cache.
                frozen = collect_frozen_pkgs(state["adb"])
                for a in state["data"]["apps"]:
                    a["frozen"] = a["package"] in frozen
            elif path == "/api/wifi/connect":
                self._wifi_connect()
            elif path == "/api/wifi/pair":
                self._wifi_pair()
            elif path == "/api/wifi/disconnect":
                self._wifi_disconnect()
            else:
                self._json(404, {"error": "not found"})

    return Handler


class _Server(ThreadingHTTPServer):
    # On Windows, SO_REUSEADDR lets bind() succeed on a port already in ACTIVE
    # use by another process, silently colliding — connections may be served by
    # the other server. Disable it there so an in-use port raises instead of
    # hijacking traffic. On POSIX it stays on for fast restarts.
    allow_reuse_address = os.name != "nt"


def _port_in_use(port: int) -> bool:
    """True if something is already accepting connections on 127.0.0.1:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _bind_server(handler, port: int) -> ThreadingHTTPServer:
    """Bind the HTTP server, falling back across ports.

    Two failure modes handled:
      * Windows refuses a bind with WinError 10013 when the port lands inside a
        Hyper-V/WSL reserved range.
      * A port already served by another app (e.g. a FastAPI dev server) must be
        skipped — otherwise the browser reaches the wrong server. We probe each
        candidate with a real connection before binding.
    Order: requested port, common fallbacks, then port 0 (OS picks any free one).
    """
    candidates = [port, 8080, 8090, 5000, 5500, 8000, 9000, 0]
    seen = set()
    last_err: OSError | None = None
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        if cand != 0 and _port_in_use(cand):
            if cand == port:
                print(f"  puerto {port} ya esta en uso por otra app, "
                      f"probando otro...", file=sys.stderr)
            continue
        try:
            return _Server(("127.0.0.1", cand), handler)
        except OSError as exc:  # PermissionError (10013) or address-in-use (10048)
            last_err = exc
            if cand == port:
                print(f"  puerto {port} no disponible ({exc.__class__.__name__}), "
                      f"probando otro...", file=sys.stderr)
    raise AdbError(f"no se pudo abrir ningun puerto local: {last_err}")


def serve(adb: AdbClient | None, data: dict, out_dir: str, port: int,
          include_system: bool, open_browser: bool, dry_run: bool = False,
          offline: bool = False, no_device: bool = False) -> None:
    state = build_state(adb, data, out_dir, include_system, offline=offline,
                        no_device=no_device)
    handler = make_handler(state, include_system, dry_run)
    httpd = _bind_server(handler, port)
    actual_port = httpd.server_address[1]
    url = f"http://127.0.0.1:{actual_port}"
    mode_str = " (modo offline)" if offline else (
        " (sin dispositivo - conecta por WiFi)" if no_device else "")
    print(f"\n  Android Package Inspector UI{mode_str} -> {url}")
    print("  Ctrl+C para detener.\n")
    if open_browser:
        threading.Timer(0.6, lambda: _open_url(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Detenido.")
        httpd.shutdown()


def _open_url(url: str) -> None:
    # On WSL, explorer.exe opens the Windows default browser.
    for opener in (["explorer.exe", url], ["wslview", url]):
        try:
            subprocess.Popen(opener, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return
        except FileNotFoundError:
            continue
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass
