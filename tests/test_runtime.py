import copy
import os
from pathlib import Path
import pwd
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "service"))
from runtime import Host, atomic_json
from install import configure, check_replacement, digest, payload

ROOT = Path(__file__).resolve().parents[1]


class RuntimeTest(unittest.TestCase):
    def setUp(self):
        self.uid = os.getuid()
        self.user = pwd.getpwuid(self.uid).pw_name
        self.saved = {}
        self.host = Host({"users": {self.user: {"trigger": "daily"}}}, {},
                         lambda data: self.saved.update(copy.deepcopy(data)),
                         verifier=lambda password: password == "test-parent-password")
        self.host.tick(0, "2026-09-12", {self.uid: {"active": True, "locked": False,
            "school": False, "session": "test-login"}})

    def test_only_enrolled_peers_can_read_or_change_their_session(self):
        self.assertEqual(self.host.dispatch(self.uid + 10000, {"cmd": "status"})["error"], "not_enrolled")
        self.assertEqual(self.host.dispatch(self.uid, {"cmd": "set", "credited": 1800})["error"], "unknown_command")
        self.assertTrue(self.host.dispatch(self.uid, {"cmd": "status", "uid": self.uid + 10000})["required"])

    @unittest.skipIf(os.getuid() == 0, "Use an unprivileged test account for parent authentication")
    def test_parent_password_is_required_and_failed_attempts_are_limited(self):
        with patch("runtime.time.monotonic", return_value=100):
            reply = self.host.dispatch(self.uid, {"cmd": "parent.end", "password": "wrong"})
            self.assertEqual(reply["error"], "bad_password")
            self.assertTrue(self.host.models[self.uid].data["required"])
            self.assertEqual(self.host.dispatch(self.uid, {"cmd": "parent.end",
                "password": "test-parent-password"})["error"], "try_later")
        with patch("runtime.time.monotonic", return_value=110):
            reply = self.host.dispatch(self.uid, {"cmd": "parent.end", "password": "test-parent-password"})
        self.assertTrue(reply["ok"])
        self.assertFalse(reply["state"]["required"])
        self.assertEqual(self.saved[self.user]["result"], "parent")
        self.assertNotIn("password", str(self.saved))

    def test_installer_preserves_other_users_and_existing_trigger(self):
        config = {"users": {"other": {"trigger": "manual"}, self.user: {"trigger": "unlock"}}}
        new = configure(config, self.user, None)
        self.assertEqual(new["users"], config["users"])
        self.assertEqual(configure(config, self.user, "daily")["users"][self.user]["trigger"], "daily")

    def test_updates_require_owned_unchanged_files_and_explicit_upgrade(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "runtime.py"
            path.write_bytes(b"original")
            tracked = {str(path): digest(b"original")}
            with self.assertRaises(ValueError):
                check_replacement(path, b"updated", tracked, False)
            check_replacement(path, b"updated", tracked, True)
            path.write_bytes(b"local change")
            with self.assertRaises(ValueError):
                check_replacement(path, b"updated", tracked, True)

    def test_progress_is_atomically_saved_with_private_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "progress.json"
            atomic_json(path, {"credited": 120})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIn("120", path.read_text())

    def test_service_payload_is_independent_of_other_plugins(self):
        files = payload(ROOT)
        self.assertTrue(files)
        for path in files:
            self.assertNotIn("screen-time", str(path))
            self.assertNotIn("kids-controls", str(path))
        for name in ("core.py", "runtime.py", "auth.py"):
            code = (ROOT / "service" / name).read_text()
            self.assertNotIn("screen_time", code)
            self.assertNotIn("provider-register", code)
            self.assertNotIn("omarchy-kids-controls-time-client", code)

    def test_late_answer_cannot_change_a_finished_round_score(self):
        model = self.host.models[self.uid]
        model.data.update(elapsed=1799, answered=49, correct=39)
        q = model.question()
        model.present(0, model.data["session"], q["id"], True)
        result = self.host.dispatch(self.uid, {"cmd": "answer", "question": q["id"],
            "answer": str(q["a"] * q["b"])}, now=1, day="2026-09-12")
        self.assertEqual(result["error"], "stale_question")
        self.assertEqual(result["state"]["round"], 2)
        self.assertEqual(result["state"]["last_round"]["correct"], 39)
        self.assertEqual(result["state"]["correct"], 0)
        self.assertEqual(self.saved[self.user]["round"], 2)

    def test_answer_just_before_deadline_can_supply_the_40th_point(self):
        model = self.host.models[self.uid]
        model.data.update(elapsed=1799, answered=49, correct=39)
        q = model.question()
        model.present(0, model.data["session"], q["id"], True)
        result = self.host.dispatch(self.uid, {"cmd": "answer", "question": q["id"],
            "answer": str(q["a"] * q["b"])}, now=0.5, day="2026-09-12")
        self.assertTrue(result["correct"])
        self.assertEqual(result["state"]["correct"], 40)
        model.present(0.5, model.data["session"], "", True)
        result = self.host.dispatch(self.uid, {"cmd": "status"}, now=1, day="2026-09-12")
        self.assertFalse(result["required"])
        self.assertEqual(result["result"], "complete")


if __name__ == "__main__":
    unittest.main()
