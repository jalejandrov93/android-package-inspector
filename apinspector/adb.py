"""ADB client and adb-output parsing helpers."""

from __future__ import annotations

import re
import subprocess


class AdbError(Exception):
    pass


_NETWORK_SERIAL_RE = re.compile(r"^[\w.\-]+:\d+$")


def is_network_serial(serial: str) -> bool:
    """True for TCP/IP device serials such as ``192.168.1.50:5555``."""
    return bool(_NETWORK_SERIAL_RE.match(serial or ""))


def parse_mdns_services(out: str) -> list[dict]:
    """Parse `adb mdns services` lines: <name> <type> <address>:<port>."""
    services = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("list of"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        name, stype, addr = parts[0], parts[1], parts[2]
        host, _, port = addr.rpartition(":")
        if not host:
            host, port = addr, ""
        services.append({
            "name": name,
            "type": stype,
            "address": host,
            "port": int(port) if port.isdigit() else None,
        })
    return services


class AdbClient:
    def __init__(self, adb_path: str, serial: str | None = None, timeout: int = 30):
        self.adb_path = adb_path
        self.serial = serial
        self.timeout = timeout

    def _base(self) -> list[str]:
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd

    def _spawn(self, cmd: list[str], timeout: int | None = None):
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
            )
        except FileNotFoundError as exc:
            raise AdbError(f"adb binary not found at '{self.adb_path}'") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"adb timed out: {' '.join(cmd[1:])}") from exc

    def _run(self, args: list[str], timeout: int | None = None) -> str:
        """Run adb targeting self.serial (adds -s when set); returns stdout."""
        return self._spawn(self._base() + args, timeout).stdout

    def _run_raw(self, args: list[str], timeout: int | None = None) -> str:
        """Run adb without -s (connect/pair/mdns/version); stdout + stderr.

        Network commands must not carry a device selector, and their success or
        failure text can land on either stream, so both are returned.
        """
        proc = self._spawn([self.adb_path] + args, timeout)
        return (proc.stdout or "") + (proc.stderr or "")

    def shell(self, command: str, timeout: int | None = None) -> str:
        return self._run(["shell", command], timeout=timeout)

    def devices(self) -> list[str]:
        out = self._run(["devices"])
        serials = []
        for line in out.splitlines()[1:]:
            line = line.strip()
            if line and "\tdevice" in line:
                serials.append(line.split("\t")[0])
        return serials

    def devices_detail(self) -> list[dict]:
        """Parse `adb devices -l` into {serial, state, info} entries."""
        out = self._spawn([self.adb_path, "devices", "-l"], timeout=15).stdout or ""
        devices = []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.lower().startswith("list of devices"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            serial, state = parts[0], parts[1]
            info: dict = {}
            for tok in parts[2:]:
                if ":" in tok:
                    k, v = tok.split(":", 1)
                    info[k] = v
            devices.append({"serial": serial, "state": state, "info": info})
        return devices

    def version_info(self) -> dict:
        """Return adb version plus whether pairing (platform-tools 30+) exists."""
        out = self._run_raw(["version"])
        m = re.search(r"Android Debug Bridge version (\S+)", out)
        version = m.group(1) if m else None
        mrel = re.search(r"^Version (\S+)", out, re.MULTILINE)
        release = mrel.group(1) if mrel else None
        nums = tuple(int(x) for x in re.findall(r"\d+", version or "")[:3])
        supports = bool(nums) and nums >= (1, 0, 41)
        return {"version": version, "release": release,
                "supports_pairing": supports}

    def connect(self, host: str, port: int = 5555) -> str:
        return self._run_raw(["connect", f"{host}:{port}"], timeout=20)

    def disconnect(self, host: str, port: int = 5555) -> str:
        return self._run_raw(["disconnect", f"{host}:{port}"], timeout=15)

    def pair(self, host: str, port: int, code: str) -> str:
        return self._run_raw(["pair", f"{host}:{port}", code], timeout=30)

    def mdns_services(self) -> list[dict]:
        out = self._spawn([self.adb_path, "mdns", "services"], timeout=15).stdout or ""
        return parse_mdns_services(out)

    def tcpip(self, port: int = 5555) -> str:
        """Switch a USB-connected device to TCP mode (legacy path, needs USB)."""
        return self._run(["tcpip", str(port)], timeout=20)

    def resolve_serial(self) -> str:
        serials = self.devices()
        if not serials:
            raise AdbError("no ADB device connected (check `adb devices`)")
        if self.serial:
            if self.serial not in serials:
                raise AdbError(f"serial '{self.serial}' not found among {serials}")
            return self.serial
        if len(serials) > 1:
            raise AdbError(f"multiple devices connected, use --serial: {serials}")
        self.serial = serials[0]
        return self.serial
