from __future__ import annotations

import unittest

from apinspector.adb import is_network_serial, parse_mdns_services
from apinspector.wifi import wifi_connect, wifi_pair

MDNS_SAMPLE = """List of discovered mdns services
adb-4H9KLM-1a2b3c\t_adb-tls-connect._tcp\t192.168.1.50:37235
adb-4H9KLM-9z8y7x\t_adb-tls-pairing._tcp\t192.168.1.50:39987
"""


class _FakeAdb:
    def __init__(self, connect_out="connected to 1.2.3.4:5555",
                 pair_out="Successfully paired to 1.2.3.4:37451",
                 devices_after=1, mdns=()):
        self.connect_out = connect_out
        self.pair_out = pair_out
        self.devices_after = devices_after
        self.mdns = list(mdns)
        self.calls = []

    def connect(self, host, port):
        self.calls.append(("connect", host, port))
        return self.connect_out

    def pair(self, host, port, code):
        self.calls.append(("pair", host, port, code))
        return self.pair_out

    def devices_detail(self):
        if self.devices_after > 0:
            return [{"serial": "1.2.3.4:5555", "state": "device", "info": {}}]
        return []

    def mdns_services(self):
        return self.mdns


class MdnsTest(unittest.TestCase):
    def test_parse(self):
        services = parse_mdns_services(MDNS_SAMPLE)
        self.assertEqual(len(services), 2)
        self.assertEqual(services[0]["port"], 37235)
        self.assertEqual(services[1]["type"], "_adb-tls-pairing._tcp")

    def test_network_serial(self):
        self.assertTrue(is_network_serial("192.168.1.50:5555"))
        self.assertFalse(is_network_serial("emulator-5554"))


class WifiTest(unittest.TestCase):
    def test_connect_success(self):
        res = wifi_connect(_FakeAdb(), "1.2.3.4", 5555)
        self.assertTrue(res["ok"])
        self.assertEqual(res["serial"], "1.2.3.4:5555")

    def test_connect_failure(self):
        res = wifi_connect(_FakeAdb(connect_out="failed to connect"), "9.9.9.9", 5555)
        self.assertFalse(res["ok"])
        self.assertFalse(res["connected"])

    def test_pair_autoconnect(self):
        res = wifi_pair(_FakeAdb(), "1.2.3.4", 37451, "123456")
        self.assertTrue(res["ok"])
        self.assertTrue(res["paired"])
        self.assertFalse(res["need_connect_port"])

    def test_pair_via_mdns_connect_service(self):
        fake = _FakeAdb(devices_after=0, mdns=[
            {"name": "x", "type": "_adb-tls-connect._tcp",
             "address": "1.2.3.4", "port": 40001},
        ])
        original = fake.connect

        def connect_then_show(host, port):
            fake.devices_after = 1
            return original(host, port)

        fake.connect = connect_then_show
        res = wifi_pair(fake, "1.2.3.4", 37451, "123456")
        self.assertTrue(res["ok"])
        self.assertIn(("connect", "1.2.3.4", 40001), fake.calls)

    def test_pair_needs_connect_port(self):
        res = wifi_pair(_FakeAdb(devices_after=0), "1.2.3.4", 37451, "123456")
        self.assertTrue(res["paired"])
        self.assertTrue(res["need_connect_port"])
        self.assertFalse(res["ok"])


if __name__ == "__main__":
    unittest.main()
