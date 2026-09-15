from __future__ import annotations

import unittest

from apinspector.config import MAX_RAW
from apinspector.scoring import (
    BLOATWARE,
    classify_criticality,
    empty_scan,
    finalize_app,
    score_risk,
)


class ScoringTest(unittest.TestCase):
    def test_critical_package_by_name(self):
        app = {"package": "com.whatsapp"}
        classify_criticality(app)
        self.assertTrue(app["critical"])
        self.assertIn("WhatsApp", app["critical_reason"])

    def test_critical_package_by_keyword(self):
        app = {"package": "com.somebank.app"}
        classify_criticality(app)
        self.assertTrue(app["critical"])
        self.assertIn("finance/banking", app["critical_reason"])

    def test_non_critical(self):
        app = {"package": "com.example.notes"}
        classify_criticality(app)
        self.assertFalse(app["critical"])

    def test_score_risk_user_unknown_installer(self):
        app = {
            "package": "com.foo", "type": "user", "overlay": False,
            "accessibility": False, "boot_completed": False,
            "foreground_service": False, "internet": False,
            "installer_label": "Unknown", "exports_services": False,
        }
        score_risk(app)
        # user_app (1) + unknown_installer (2) + untrusted_signature (2)
        self.assertEqual(app["score_raw"], 5)
        self.assertEqual(app["score_pct"], round(5 / MAX_RAW * 100))
        self.assertIn("Installer desconocido", app["reasons"])

    def test_score_risk_system_stays_quiet(self):
        app = {
            "package": "com.sys", "type": "system", "overlay": False,
            "accessibility": False, "boot_completed": False,
            "foreground_service": True, "internet": True,
            "installer_label": "Play Store", "exports_services": False,
        }
        score_risk(app)
        self.assertEqual(app["reasons"], ["Componente de sistema"])

    def test_finalize_marks_frozen_and_active(self):
        app = {"package": "com.foo", "parse_error": True, "type": "user"}
        finalize_app(app, "com.foo", {"com.foo"}, {"com.foo"},
                     {"com.foo"}, "com.foo", {"com.foo"})
        self.assertTrue(app["frozen"])
        self.assertTrue(app["accessibility_active"])
        self.assertTrue(app["device_admin_active"])
        self.assertTrue(app["is_launcher"])
        self.assertTrue(app["overlay"])

    def test_finalize_parse_error_defaults(self):
        app = {"package": "com.bad", "parse_error": True, "type": "user"}
        finalize_app(app, "com.bad", set(), set(), set(), None, set())
        self.assertEqual(app["stars"], 1)
        self.assertFalse(app["critical"])

    def test_empty_scan_shape(self):
        data = empty_scan()
        self.assertTrue(data["no_device"])
        self.assertEqual(data["counts"]["total"], 0)
        self.assertEqual(data["apps"], [])

    def test_bloatware_global_default(self):
        self.assertIsInstance(BLOATWARE, dict)


if __name__ == "__main__":
    unittest.main()
