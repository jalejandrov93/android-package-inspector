"""Wireless ADB helpers (Android 11+ pairing / legacy TCP/IP)."""

from __future__ import annotations

import re
import time

from .adb import AdbClient, AdbError, is_network_serial


def _find_network_device(adb: AdbClient, host: str,
                         states: tuple[str, ...] = ("device",)) -> str | None:
    for dev in adb.devices_detail():
        serial = dev["serial"]
        if (is_network_serial(serial) and serial.startswith(host + ":")
                and dev["state"] in states):
            return serial
    return None


def _wait_for_network_device(adb: AdbClient, host: str, timeout: float = 8.0,
                             states: tuple[str, ...] = ("device",)) -> str | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        serial = _find_network_device(adb, host, states)
        if serial:
            return serial
        time.sleep(0.5)
    return None


def wifi_connect(adb: AdbClient, host: str, port: int = 5555) -> dict:
    """`adb connect host:port` and wait until the device shows up as 'device'."""
    try:
        output = adb.connect(host, port)
    except AdbError as exc:
        return {"ok": False, "output": str(exc), "connected": False}
    connected = bool(re.search(r"\bconnected to\b", output, re.I))
    serial = _wait_for_network_device(adb, host, timeout=8.0) if connected else None
    return {"ok": bool(serial), "connected": connected,
            "serial": serial, "output": output.strip()}


def wifi_pair(adb: AdbClient, host: str, pairing_port: int, code: str) -> dict:
    """`adb pair host:port code`, then resolve the (different) connect port.

    After pairing, modern adb usually auto-connects through mDNS
    (ADB_MDNS_AUTO_CONNECT defaults to adb-tls-connect). If that does not
    happen, fall back to the discovered `_adb-tls-connect._tcp` service.
    """
    try:
        output = adb.pair(host, pairing_port, code)
    except AdbError as exc:
        return {"ok": False, "paired": False, "output": str(exc)}
    paired = bool(re.search(r"successfully paired", output, re.I))
    serial = None
    if paired:
        serial = _wait_for_network_device(adb, host, timeout=8.0)
        if not serial:
            try:
                services = adb.mdns_services()
            except AdbError:
                services = []
            for svc in services:
                if ("connect" in svc["type"] and svc["address"] == host
                        and svc["port"]):
                    try:
                        adb.connect(host, svc["port"])
                    except AdbError:
                        break
                    serial = _wait_for_network_device(adb, host, timeout=5.0)
                    break
    return {"ok": bool(serial), "paired": paired,
            "need_connect_port": paired and not serial,
            "serial": serial, "output": output.strip()}
