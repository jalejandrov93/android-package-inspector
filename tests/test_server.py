from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from apinspector.scoring import empty_scan
from apinspector.web import server as web


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        state = web.build_state(None, empty_scan(), cls.tmp, False, offline=True)
        handler = web.make_handler(state, False)
        cls.httpd = web._bind_server(handler, 0)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def _request(self, path, data=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        body = None
        headers = {}
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        else:
            req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, resp.headers.get("Content-Type"), resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers.get("Content-Type"), exc.read()

    def test_index_serves_spa_with_asset_links(self):
        status, ctype, body = self._request("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)
        self.assertIn(b"/static/app.js", body)
        self.assertIn(b"/static/app.css", body)

    def test_static_css(self):
        status, ctype, body = self._request("/static/app.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", ctype)
        self.assertGreater(len(body), 100)

    def test_static_js(self):
        status, ctype, body = self._request("/static/app.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", ctype)

    def test_static_traversal_blocked(self):
        status, _, _ = self._request("/static/..%2f..%2fetc%2fpasswd")
        self.assertEqual(status, 404)

    def test_static_unknown_extension_blocked(self):
        status, _, _ = self._request("/static/secret.txt")
        self.assertEqual(status, 404)

    def test_apps_offline_empty(self):
        status, _, body = self._request("/api/apps")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["counts"]["total"], 0)

    def test_state_offline_uses_cache(self):
        status, _, body = self._request("/api/state")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["frozen"], [])
        self.assertEqual(payload["installed"], [])

    def test_wifi_connect_without_adb_is_rejected(self):
        status, _, body = self._request("/api/wifi/connect", {"host": "1.2.3.4"})
        self.assertEqual(status, 400)
        self.assertIn("adb", json.loads(body)["error"])

    def test_unknown_route(self):
        status, _, _ = self._request("/nope")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
