from __future__ import annotations

import unittest

from apinspector.parsing import _section, parse_package

SAMPLE = """Package [com.example.suspect] (1234):
  userId=10123
  codePath=/data/app/com.example.suspect/base.apk
  versionName=1.2.3
  versionCode=42
  firstInstallTime=2024-01-01 10:00:00
  lastUpdateTime=2024-02-02 11:00:00
  signatures=PackageSignatures{abcd1234, signatures:[DEADBEEF]}
  installerPackageName=com.unknown.store
  flags=[ HAS_CODE ALLOW_CLEAR_USER_DATA ]
grantedPermissions:
    android.permission.INTERNET: granted=true
    android.permission.CAMERA: granted=true
    android.permission.RECEIVE_BOOT_COMPLETED: granted=true
Activity Resolver Table:
  com.example.suspect/.MainActivity
    android.intent.action.MAIN
    android.intent.category.HOME"
Receiver Resolver Table:
  com.example.suspect/.BootReceiver
    android.intent.action.BOOT_COMPLETED"
Service Resolver Table:
  com.example.suspect/.SyncService
    com.example.suspect.SYNC
Provider Resolver Table:
  com.example.suspect/.Provider
Key Set Manager:
  Keys: []
"""

SYSTEM_SAMPLE = """Package [com.vendor.app] (10):
  userId=1000
  codePath=/system/priv-app/VendorApp/VendorApp.apk
  flags=[ SYSTEM HAS_CODE ]
"""


class ParsingTest(unittest.TestCase):
    def test_user_app_fields(self):
        app = parse_package("com.example.suspect", SAMPLE)
        self.assertEqual(app["type"], "user")
        self.assertEqual(app["uid"], 10123)
        self.assertEqual(app["version_code"], 42)
        self.assertEqual(app["version_name"], "1.2.3")
        self.assertEqual(app["installer"], "com.unknown.store")
        self.assertEqual(app["installer_label"], "com.unknown.store")
        self.assertIn("android.permission.CAMERA", app["dangerous_permissions"])
        self.assertTrue(app["internet"])
        self.assertTrue(app["boot_completed"])
        self.assertTrue(app["is_launcher"])
        self.assertEqual(app["exported_activities"], 1)
        self.assertEqual(app["exported_receivers"], 1)
        self.assertEqual(app["exported_services"], 1)
        self.assertTrue(app["exports_services"])

    def test_system_app_detected_by_flag_and_path(self):
        app = parse_package("com.vendor.app", SYSTEM_SAMPLE)
        self.assertEqual(app["type"], "system")

    def test_unknown_installer_label(self):
        app = parse_package("com.foo", "Package [com.foo]:\n  flags=[]")
        self.assertEqual(app["installer_label"], "Unknown")

    def test_section_stops_at_next_header(self):
        block = _section(SAMPLE, "Receiver Resolver Table:", ("Service Resolver Table:",))
        self.assertIn("BootReceiver", block)
        self.assertNotIn("SyncService", block)


if __name__ == "__main__":
    unittest.main()
