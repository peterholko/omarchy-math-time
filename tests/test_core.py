import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "service"))
from core import DURATION, Practice

DAY = "2026-09-12"
DESKTOP = {"active": True, "locked": False, "school": False, "session": "login-one"}


class PracticeTest(unittest.TestCase):
    def setUp(self):
        self.practice = Practice()
        self.now = 0
        self.env = dict(DESKTOP)
        self.practice.advance(self.now, DAY, self.env)

    def work(self, seconds, visible=True):
        for _ in range(seconds):
            question = self.practice.question()
            self.practice.present(self.now, self.practice.data["session"], question["id"], visible)
            self.now += 1
            self.practice.advance(self.now, DAY, self.env)

    def answer(self, value=None):
        question = self.practice.question()
        return self.practice.answer(question["id"], str(question["a"] * question["b"]) if value is None else value)

    def test_all_144_multiplication_facts_are_covered_without_repetition(self):
        seen = set()
        for _ in range(144):
            q = self.practice.question()
            seen.add((q["a"], q["b"]))
            self.assertTrue(self.answer()["correct"])
        self.assertEqual(seen, {(a, b) for a in range(1, 13) for b in range(1, 13)})
        self.assertEqual(self.practice.data["credited"], 0)
        self.assertTrue(self.practice.data["required"])

    def test_requires_thirty_minutes_and_a_final_correct_answer(self):
        for _ in range(29):
            self.work(60)
            self.answer()
        self.assertTrue(self.practice.data["required"])
        self.work(60)
        self.assertEqual(self.practice.snapshot(self.now)["remaining"], 0)
        self.assertTrue(self.practice.data["required"])
        self.answer("999")
        self.assertTrue(self.practice.data["required"])
        self.answer()
        self.assertEqual(self.practice.data["credited"], DURATION)
        self.assertFalse(self.practice.data["required"])
        self.assertEqual(self.practice.data["result"], "complete")

    def test_waiting_without_answering_cannot_complete_practice(self):
        self.work(1800)
        self.assertEqual(self.practice.data["credited"], 0)
        self.assertEqual(self.practice.data["pending"], 60)
        self.assertTrue(self.practice.data["required"])
        self.answer()
        self.assertEqual(self.practice.data["credited"], 60)

    def test_wrong_and_duplicate_answers_do_not_add_practice_time(self):
        self.work(20)
        question = copy.deepcopy(self.practice.question())
        self.assertFalse(self.answer("999")["correct"])
        self.assertEqual(self.practice.data["credited"], 0)
        self.assertEqual(self.practice.question(), question)
        self.assertTrue(self.answer()["correct"])
        self.assertEqual(self.practice.data["credited"], 20)
        reply = self.practice.answer(question["id"], str(question["a"] * question["b"]))
        self.assertEqual(reply["error"], "stale_question")
        self.assertEqual(self.practice.data["credited"], 20)

    def test_reboot_restores_question_and_progress_without_offline_credit(self):
        self.work(20)
        self.answer()
        self.work(10)
        previous = copy.deepcopy(self.practice.data)
        self.practice = Practice(previous)
        self.now += 8640
        self.practice.advance(self.now, DAY, {**DESKTOP, "session": "new-login"})
        self.assertEqual(self.practice.data["credited"], 20)
        self.assertEqual(self.practice.data["pending"], 10)
        self.assertEqual(self.practice.question(), previous["question"])
        self.assertTrue(self.practice.data["required"])

    def test_school_mode_lock_and_missing_status_pause_without_cancelling(self):
        for change in ({"school": True}, {"school": None}, {"locked": True}, {"active": False}):
            with self.subTest(change=change):
                before = self.practice.data["pending"]
                self.env = {**DESKTOP, **change}
                self.work(10)
                self.assertEqual(self.practice.data["pending"], before)
                self.assertFalse(self.practice.snapshot(self.now)["show"])
                self.assertFalse(self.answer()["ok"])
        self.env = dict(DESKTOP)
        self.work(3)
        self.assertTrue(self.practice.snapshot(self.now)["show"])

    def test_school_at_first_login_defers_automatic_start(self):
        model = Practice()
        model.advance(0, DAY, {**DESKTOP, "school": True})
        self.assertFalse(model.data["required"])
        model.advance(1, DAY, DESKTOP)
        self.assertTrue(model.data["required"])

    def test_missing_overlay_presence_stops_the_timer(self):
        self.work(10)
        self.work(50, visible=False)
        self.assertEqual(self.practice.data["pending"], 10)

    def test_daily_completion_and_parent_override_do_not_restart_on_unlock(self):
        for result in ("complete", "parent"):
            with self.subTest(result=result):
                self.practice.end_by_parent()
                self.practice.data["result"] = result
                self.practice.advance(self.now + 1, DAY, {**DESKTOP, "locked": True})
                self.practice.advance(self.now + 2, DAY, DESKTOP)
                self.assertFalse(self.practice.data["required"])
                self.assertEqual(self.practice.start(DAY)["error"], "finished_today")
        self.practice.advance(self.now + 3, "2026-09-13", DESKTOP)
        self.assertTrue(self.practice.data["required"])

    def test_manual_start_is_explicit_and_reopen_keeps_progress(self):
        model = Practice(trigger="manual")
        model.advance(0, DAY, DESKTOP)
        self.assertFalse(model.data["required"])
        self.assertTrue(model.start(DAY)["ok"])
        identifier = model.data["session"]
        model.data["credited"] = 125
        self.assertTrue(model.start(DAY)["ok"])
        self.assertEqual(model.data["session"], identifier)
        self.assertEqual(model.data["credited"], 125)

    def test_clock_jumps_cannot_finish_the_timer(self):
        self.practice.present(0, self.practice.data["session"], self.practice.question()["id"], True)
        self.practice.advance(999999, DAY, DESKTOP)
        self.assertEqual(self.practice.data["pending"], 0)
        self.practice.end_by_parent()
        self.practice.advance(1000000, "2026-09-11", DESKTOP)
        self.assertFalse(self.practice.data["required"])

    def test_unlock_trigger_starts_once_and_preserves_unfinished_work(self):
        model = Practice(trigger="unlock")
        model.advance(0, DAY, DESKTOP)
        model.data["credited"] = 123
        identifier = model.data["session"]
        model.advance(1, DAY, {**DESKTOP, "locked": True})
        model.advance(2, DAY, DESKTOP)
        self.assertEqual(model.data["session"], identifier)
        self.assertEqual(model.data["credited"], 123)
        model.end_by_parent()
        model.advance(3, DAY, DESKTOP)
        self.assertFalse(model.data["required"])
        model.advance(4, DAY, {**DESKTOP, "locked": True})
        model.advance(5, DAY, DESKTOP)
        self.assertTrue(model.data["required"])
        self.assertNotEqual(model.data["session"], identifier)

    def test_unlock_trigger_defers_school_and_detects_new_boot(self):
        model = Practice(trigger="unlock")
        model.advance(0, DAY, {**DESKTOP, "school": True})
        self.assertFalse(model.data["required"])
        model.advance(1, DAY, DESKTOP)
        self.assertTrue(model.data["required"])
        model.end_by_parent()
        restored = Practice(model.data, trigger="unlock")
        restored.advance(0, DAY, DESKTOP)
        self.assertFalse(restored.data["required"])
        restored.advance(1, DAY, {**DESKTOP, "session": "new-boot:login-one"})
        self.assertTrue(restored.data["required"])


if __name__ == "__main__":
    unittest.main()
