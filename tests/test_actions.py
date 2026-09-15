from __future__ import annotations

import tempfile
import unittest

from apinspector.actions import apply_action, check_action_gate


class _FakeAdb:
    def __init__(self, out="Success"):
        self.out = out
        self.calls = []

    def shell(self, command, timeout=None):
        self.calls.append(command)
        return self.out


INDEX = {
    "com.safe.app": {"package": "com.safe.app", "type": "user", "critical": False},
    "com.bank.app": {"package": "com.bank.app", "type": "user", "critical": True,
                     "critical_reason": "Possible finance/banking app"},
    "com.sys.app": {"package": "com.sys.app", "type": "system", "critical": False},
}


class GateTest(unittest.TestCase):
    def test_unknown_action(self):
        gate = check_action_gate("nuke", [], {}, False)
        self.assertEqual(gate["status"], 400)

    def test_system_uninstall_blocked(self):
        gate = check_action_gate("uninstall", ["com.sys.app"], INDEX, True)
        self.assertEqual(gate["status"], 403)
        self.assertIn("system app", gate["error"])

    def test_critical_requires_confirmation(self):
        gate = check_action_gate("freeze", ["com.bank.app"], INDEX, False)
        self.assertEqual(gate["status"], 409)
        self.assertTrue(gate["needs_confirm"])
        self.assertEqual(gate["critical"][0]["package"], "com.bank.app")

    def test_critical_confirmed_proceeds(self):
        self.assertIsNone(check_action_gate("freeze", ["com.bank.app"], INDEX, True))

    def test_safe_action_proceeds(self):
        self.assertIsNone(check_action_gate("freeze", ["com.safe.app"], INDEX, False))


class ApplyTest(unittest.TestCase):
    def test_dry_run_never_executes(self):
        adb = _FakeAdb()
        with tempfile.TemporaryDirectory() as out:
            res = apply_action(adb, "freeze", ["com.safe.app"], INDEX, False,
                               out, dry_run=True)
        self.assertEqual(res["status"], 200)
        self.assertEqual(adb.calls, [])
        self.assertTrue(res["results"][0]["ok"])
        self.assertIn("[dry-run]", res["results"][0]["output"])

    def test_real_run_reports_success(self):
        adb = _FakeAdb(out="Success")
        with tempfile.TemporaryDirectory() as out:
            res = apply_action(adb, "freeze", ["com.safe.app"], INDEX, False, out)
        self.assertEqual(adb.calls, ["pm disable-user --user 0 com.safe.app"])
        self.assertTrue(res["results"][0]["ok"])

    def test_real_run_failure(self):
        adb = _FakeAdb(out="Error: not allowed")
        with tempfile.TemporaryDirectory() as out:
            res = apply_action(adb, "unfreeze", ["com.safe.app"], INDEX, False, out)
        self.assertFalse(res["results"][0]["ok"])

    def test_gate_returned_when_target_is_system(self):
        adb = _FakeAdb()
        with tempfile.TemporaryDirectory() as out:
            res = apply_action(adb, "uninstall", ["com.sys.app"], INDEX, True, out)
        self.assertEqual(res["status"], 403)
        self.assertEqual(adb.calls, [])


if __name__ == "__main__":
    unittest.main()
