import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "service"))
from session import environment, school_status


class SessionTest(unittest.TestCase):
    def school(self, files):
        with patch("session.Path.exists", lambda path: str(path) in files), \
             patch("session.Path.read_text", lambda path: json.dumps(files[str(path)])):
            return school_status("linnea")

    def test_optional_school_status_is_read_without_altering_settings(self):
        status = "/var/lib/omarchy-kids-controls/status/linnea/school-mode/status.json"
        config = "/etc/omarchy-kids-controls/school-mode.json"
        self.assertIs(self.school({}), False)
        self.assertIsNone(self.school({config: {"users": {"linnea": {}}}}))
        for mode in ("school", "free"):
            self.assertIs(self.school({status: {"schemaVersion": 1, "enabled": True, "mode": mode}}), mode == "school")
        self.assertIsNone(self.school({status: {"schemaVersion": 1, "enabled": True, "mode": "unknown"}}))
        self.assertIs(self.school({status: {"schemaVersion": 1, "enabled": False}}), False)

    def test_logind_identifies_only_an_active_unlocked_graphical_session(self):
        rows = {"Sessions": "tty-session desktop-session"}
        tty = {"Class": "user", "Type": "tty", "Active": "yes", "State": "active", "LockedHint": "no"}
        desktop = {**tty, "Type": "wayland"}
        with patch("session.school_status", return_value=False), \
             patch("session.Path.read_text", return_value="boot-one\n"), \
             patch("session.properties", side_effect=[rows, tty, desktop]):
            result = environment(1000, "linnea")
        self.assertEqual(result, {"active": True, "locked": False, "school": False,
                                  "session": "boot-one:desktop-session"})
        with patch("session.school_status", return_value=True), \
             patch("session.Path.read_text", return_value="boot-two\n"), \
             patch("session.properties", side_effect=[{"Sessions": "desktop"}, {**desktop, "LockedHint": "yes"}]):
            result = environment(1000, "linnea")
        self.assertTrue(result["locked"])
        self.assertTrue(result["school"])

    def test_logind_failure_pauses_practice(self):
        with patch("session.school_status", return_value=False), \
             patch("session.Path.read_text", return_value="boot-one\n"), \
             patch("session.properties", side_effect=OSError):
            self.assertFalse(environment(1000, "linnea")["active"])
