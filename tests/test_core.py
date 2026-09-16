import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "service"))
from core import DURATION, RETRY_DURATION, Practice

DAY = "2026-09-12"
DESKTOP = {"active": True, "locked": False, "school": False, "session": "login-one"}


class PracticeTest(unittest.TestCase):
    def setUp(self):
        self.practice = Practice()
        self.now = 0
        self.env = dict(DESKTOP)
        self.practice.advance(self.now, DAY, self.env)
        self.assertTrue(self.practice.start(DAY)["ok"])

    def work(self, seconds, visible=True, day=DAY):
        for _ in range(seconds):
            q = self.practice.question()
            self.practice.present(self.now, self.practice.data["session"], q["id"] if q else "", visible)
            self.now += 1
            self.practice.advance(self.now, day, self.env)

    def answer(self, correct=True):
        q = self.practice.question()
        self.assertIsNotNone(q)
        return self.practice.answer(q["id"], str(q["a"] * q["b"]) if correct else "999")

    def answer_round(self, correct):
        count = self.practice.question_count
        for i in range(count):
            self.complete_question(i < correct)

    def complete_question(self, correct=True):
        self.assertEqual(self.answer(correct)["correct"], correct)
        if not correct:
            self.assertTrue(self.answer()["correct"])

    def test_all_144_facts_are_covered_before_repetition_across_rounds(self):
        seen = set()
        for _ in range(144):
            if self.practice.question() is None:
                self.work(int(self.practice.duration - self.practice.data["elapsed"]))
            q = self.practice.question()
            seen.add((q["a"], q["b"]))
            self.complete_question(False)
        self.assertEqual(seen, {(a, b) for a in range(1, 13) for b in range(1, 13)})

    def test_initial_round_requires_40_of_50_at_the_30_minute_deadline(self):
        for score in (39, 40, 41, 50):
            with self.subTest(score=score):
                self.setUp()
                self.answer_round(score)
                self.assertIsNone(self.practice.question())
                self.assertEqual(self.practice.data["answered"], 50)
                self.work(DURATION - 1)
                self.assertTrue(self.practice.data["required"])
                self.work(1)
                self.assertEqual(self.practice.data["last_round"]["correct"], score)
                self.assertEqual(self.practice.data["required"], score < 40)
                if score < 40:
                    self.assertEqual(self.practice.snapshot(self.now)["question_count"], 25)
                    self.assertEqual(self.practice.snapshot(self.now)["remaining"], RETRY_DURATION)
                else:
                    self.assertEqual(self.practice.data["result"], "complete")

    def test_retry_rounds_repeat_independently_until_20_of_25_pass(self):
        self.answer_round(39)
        self.work(DURATION)
        self.assertEqual(self.practice.data["round"], 2)
        self.assertEqual(self.practice.data["correct"], 0)
        self.answer_round(19)
        self.work(RETRY_DURATION)
        self.assertEqual(self.practice.data["round"], 3)
        self.assertEqual(self.practice.data["last_round"]["correct"], 19)
        self.assertEqual(self.practice.data["correct"], 0)
        self.assertEqual(self.practice.data["answered"], 0)
        self.answer_round(20)
        self.work(RETRY_DURATION - 1)
        self.assertTrue(self.practice.data["required"])
        self.work(1)
        self.assertFalse(self.practice.data["required"])
        self.assertEqual(self.practice.data["last_round"]["correct"], 20)
        self.assertEqual(self.practice.data["last_round"]["questions"], 25)

    def test_unanswered_questions_are_incorrect_at_deadline(self):
        for score in (39, 40):
            with self.subTest(score=score):
                self.setUp()
                for _ in range(score):
                    self.answer()
                self.work(DURATION)
                result = self.practice.data["last_round"]
                self.assertEqual(result["answered"], score)
                self.assertEqual(result["questions"], 50)
                self.assertEqual(result["passed"], score >= 40)

    def test_inactivity_never_passes_a_round(self):
        self.work(DURATION)
        self.assertEqual(self.practice.data["round"], 2)
        self.assertEqual(self.practice.data["last_round"]["correct"], 0)
        self.work(RETRY_DURATION)
        self.assertEqual(self.practice.data["round"], 3)
        self.assertTrue(self.practice.data["required"])

    def test_wrong_answers_consume_one_question_and_replays_cannot_change_score(self):
        q = copy.deepcopy(self.practice.question())
        result = self.answer(False)
        self.assertIn("Not quite.", result["hint"])
        self.assertNotIn("solution", self.practice.question())
        self.assertEqual(self.practice.question()["stage"], "retry")
        self.assertNotEqual(self.practice.question()["id"], q["id"])
        self.assertEqual(self.practice.data["answered"], 1)
        self.assertEqual(self.practice.data["correct"], 0)
        result = self.answer()
        self.assertTrue(result["correct"])
        self.assertFalse(result["scored"])
        self.assertEqual(self.practice.data["answered"], 1)
        self.assertEqual(self.practice.data["correct"], 0)
        self.assertEqual(self.practice.data["attempts"], 1)
        reply = self.practice.answer(q["id"], str(q["a"] * q["b"]))
        self.assertEqual(reply["error"], "stale_question")
        self.assertEqual(self.practice.data["answered"], 1)
        self.assertEqual(self.practice.data["correct"], 0)

    def test_invalid_input_does_not_consume_question(self):
        q = copy.deepcopy(self.practice.question())
        for value in ("", "text", "-1", "1000", "１２"):
            self.assertEqual(self.practice.answer(q["id"], value)["error"], "use_digits")
        self.assertEqual(self.practice.question(), q)
        self.assertEqual(self.practice.data["answered"], 0)

    def test_duplicate_first_submission_does_not_use_the_guided_retry(self):
        original = copy.deepcopy(self.practice.question())
        self.answer(False)
        retry = copy.deepcopy(self.practice.question())
        result = self.practice.answer(original["id"], "999")
        self.assertEqual(result["error"], "stale_question")
        self.assertEqual(self.practice.question(), retry)
        self.assertEqual(self.practice.data["answered"], 1)

    def test_hint_retries_then_reveals_answer_until_acknowledged(self):
        self.practice.data["question"] = {"id": "seven-eight", "a": 7, "b": 8, "stage": "first"}
        first = self.answer(False)
        self.assertIn("7 × 4", first["hint"])
        self.assertNotIn("56", first["hint"])
        retry = copy.deepcopy(self.practice.question())
        self.assertEqual(self.practice.acknowledge(retry["id"])["error"], "not_reviewing")
        self.assertEqual(self.practice.answer(retry["id"], "")["error"], "use_digits")
        self.assertEqual(self.practice.question(), retry)
        second = self.answer(False)
        self.assertFalse(second["scored"])
        reveal = copy.deepcopy(self.practice.question())
        self.assertEqual(reveal["stage"], "reveal")
        self.assertEqual(reveal["solution"], 56)
        self.assertIn("7 × 8 = 56", second["hint"])
        self.assertEqual(self.practice.answer(reveal["id"], "56")["error"], "acknowledgement_required")
        self.assertEqual(self.practice.acknowledge(retry["id"])["error"], "stale_question")
        self.work(5)
        self.assertEqual(self.practice.question(), reveal)
        self.assertTrue(self.practice.acknowledge(reveal["id"])["acknowledged"])
        self.assertNotEqual(self.practice.question()["id"], reveal["id"])
        self.assertEqual(self.practice.question()["stage"], "first")
        self.assertEqual(self.practice.data["answered"], 1)
        self.assertEqual(self.practice.data["correct"], 0)
        self.assertEqual(self.practice.data["attempts"], 1)
        self.assertEqual(self.practice.data["total_correct"], 0)

    def test_each_table_has_a_strategy_hint_without_the_final_equation(self):
        for a in range(1, 13):
            for b in range(1, 13):
                hint = Practice.guided_hint(a, b)
                self.assertTrue(hint)
                self.assertNotIn(f"= {a * b}", hint)

    def test_final_question_still_gets_one_retry_and_review_without_exceeding_quota(self):
        for _ in range(49):
            self.answer()
        self.answer(False)
        self.assertEqual(self.practice.data["answered"], 50)
        self.assertEqual(self.practice.question()["stage"], "retry")
        self.answer(False)
        self.assertEqual(self.practice.question()["stage"], "reveal")
        self.practice.acknowledge(self.practice.question()["id"])
        self.assertIsNone(self.practice.question())
        self.assertEqual(self.practice.data["answered"], 50)
        self.assertEqual(self.practice.data["correct"], 49)

    def test_guided_retry_and_reveal_resume_after_restart(self):
        for stage in ("retry", "reveal"):
            with self.subTest(stage=stage):
                self.setUp()
                self.answer(False)
                if stage == "reveal":
                    self.answer(False)
                self.work(45)
                saved = copy.deepcopy(self.practice.data)
                restored = Practice(saved)
                restored.advance(0, DAY, DESKTOP)
                self.assertEqual(restored.question(), saved["question"])
                self.assertEqual(restored.question()["stage"], stage)
                self.assertEqual(restored.data["elapsed"], 45)
                self.assertEqual(restored.data["answered"], 1)
                self.assertEqual(restored.data["correct"], 0)

    def test_tutoring_does_not_extend_deadline_or_supply_a_passing_point(self):
        for reveal in (False, True):
            with self.subTest(reveal=reveal):
                self.setUp()
                for _ in range(39):
                    self.answer()
                self.work(DURATION - 1)
                self.answer(False)
                if reveal:
                    self.answer(False)
                token = self.practice.question()["id"]
                self.work(1)
                self.assertEqual(self.practice.data["round"], 2)
                self.assertEqual(self.practice.data["last_round"]["correct"], 39)
                self.assertEqual(self.practice.answer(token, "56")["error"], "stale_question")
                self.assertEqual(self.practice.acknowledge(token)["error"], "stale_question")

    def test_school_mode_keeps_review_and_accepts_continue_without_rescoring(self):
        self.answer(False)
        self.answer(False)
        question = copy.deepcopy(self.practice.question())
        self.env = {**DESKTOP, "school": True}
        self.work(30)
        self.assertEqual(self.practice.data["elapsed"], 30)
        self.assertEqual(self.practice.question(), question)
        self.assertTrue(self.practice.acknowledge(question["id"])["acknowledged"])
        self.assertEqual(self.practice.data["answered"], 1)
        self.assertEqual(self.practice.data["correct"], 0)

    def test_version_11_round_progress_migrates_without_reset(self):
        for _ in range(7):
            self.answer()
        self.work(123)
        saved = copy.deepcopy(self.practice.data)
        saved["question"].pop("stage")
        migrated = Practice(saved)
        self.assertEqual(migrated.question()["id"], saved["question"]["id"])
        self.assertEqual(migrated.question()["stage"], "first")
        self.assertEqual(migrated.data["elapsed"], 123)
        self.assertEqual(migrated.data["answered"], 7)
        self.assertEqual(migrated.data["correct"], 7)

    def test_quota_cannot_be_exceeded_by_more_submissions(self):
        last = None
        for _ in range(50):
            last = self.practice.question()
            self.complete_question(False)
        self.assertIsNone(self.practice.question())
        reply = self.practice.answer(last["id"], str(last["a"] * last["b"]))
        self.assertEqual(reply["error"], "stale_question")
        self.assertEqual(self.practice.data["answered"], 50)

    def test_reboot_preserves_retry_score_question_and_remaining_time(self):
        self.answer_round(39)
        self.work(DURATION)
        for _ in range(7):
            self.answer()
        self.work(123)
        previous = copy.deepcopy(self.practice.data)
        self.practice = Practice(previous)
        self.now += 8640
        self.practice.advance(self.now, DAY, {**DESKTOP, "session": "new-login"})
        self.assertEqual(self.practice.data["round"], 2)
        self.assertEqual(self.practice.data["correct"], 7)
        self.assertEqual(self.practice.data["answered"], 7)
        self.assertEqual(self.practice.data["elapsed"], 123)
        self.assertEqual(self.practice.question(), previous["question"])

    def test_lock_missing_status_and_hidden_view_pause_the_clock(self):
        for change in ({"school": None}, {"locked": True}, {"active": False}, {"school": True, "locked": True}):
            with self.subTest(change=change):
                before = self.practice.data["elapsed"]
                self.env = {**DESKTOP, **change}
                self.work(10)
                self.assertEqual(self.practice.data["elapsed"], before)
                self.assertFalse(self.practice.snapshot(self.now)["show"])
                self.assertFalse(self.answer()["ok"])
        self.env = dict(DESKTOP)
        self.work(3)
        before = self.practice.data["elapsed"]
        self.work(50, visible=False)
        self.assertEqual(self.practice.data["elapsed"], before)
        self.assertTrue(self.practice.snapshot(self.now)["show"])

    def test_calendar_login_unlock_and_free_time_never_start_practice(self):
        model = Practice()
        environments = [DESKTOP, {**DESKTOP, "school": True}, DESKTOP,
                        {**DESKTOP, "locked": True}, DESKTOP,
                        {**DESKTOP, "session": "new-boot:new-login"}]
        for now, environment in enumerate(environments):
            model.advance(now, "2026-09-13", environment)
            self.assertFalse(model.data["required"])
            self.assertFalse(model.snapshot(now)["show"])
            self.assertIsNone(model.question())
        self.assertTrue(model.start("2026-09-13")["ok"])

    def test_completed_and_parent_ended_sessions_can_restart_manually_the_same_day(self):
        for result in ("complete", "parent"):
            self.practice.end_by_parent()
            self.practice.data["result"] = result
            identifier = self.practice.data["session"]
            self.practice.advance(self.now + 1, DAY, {**DESKTOP, "locked": True})
            self.practice.advance(self.now + 2, DAY, DESKTOP)
            self.assertFalse(self.practice.data["required"])
            self.assertTrue(self.practice.start(DAY)["ok"])
            self.assertNotEqual(self.practice.data["session"], identifier)
            self.assertEqual(self.practice.data["elapsed"], 0)
            self.assertEqual(self.practice.data["answered"], 0)
            self.assertEqual(self.practice.data["result"], "")
            self.practice.end_by_parent()
            self.practice.advance(self.now + 3, "2026-09-13", DESKTOP)
            self.assertFalse(self.practice.data["required"])

    def test_midnight_keeps_unfinished_round_and_completion_satisfies_new_day(self):
        self.answer_round(40)
        self.work(1799)
        self.work(1, day="2026-09-13")
        self.assertFalse(self.practice.data["required"])
        self.assertEqual(self.practice.data["day"], "2026-09-13")
        self.setUp()
        self.work(10, day="2026-09-13")
        self.assertEqual(self.practice.data["elapsed"], 10)
        self.assertEqual(self.practice.data["round"], 1)
        self.practice.end_by_parent("2026-09-13")
        self.practice.advance(self.now + 1, "2026-09-13", DESKTOP)
        self.assertFalse(self.practice.data["required"])

    def test_manual_start_is_explicit_and_reopen_keeps_progress(self):
        model = Practice()
        model.advance(0, DAY, DESKTOP)
        self.assertFalse(model.data["required"])
        self.assertTrue(model.start(DAY)["ok"])
        identifier = model.data["session"]
        model.data["elapsed"] = 125
        self.assertTrue(model.start(DAY)["ok"])
        self.assertEqual(model.data["session"], identifier)
        self.assertEqual(model.data["elapsed"], 125)

    def test_clock_jumps_cannot_finish_a_round(self):
        self.practice.present(0, self.practice.data["session"], self.practice.question()["id"], True)
        self.practice.advance(999999, DAY, DESKTOP)
        self.assertEqual(self.practice.data["elapsed"], 0)
        self.practice.advance(0, DAY, DESKTOP)
        self.assertEqual(self.practice.last_tick, 999999)
        self.practice.end_by_parent()
        self.practice.advance(1000000, "2026-09-11", DESKTOP)
        self.assertFalse(self.practice.data["required"])

    def test_manual_start_is_rejected_during_lock_or_missing_status(self):
        model = Practice()
        for change in ({"school": None}, {"locked": True}, {"active": False}, {"school": True, "locked": True}):
            with self.subTest(change=change):
                model.advance(0, DAY, {**DESKTOP, **change})
                self.assertEqual(model.start(DAY)["error"], "school_or_locked")
                self.assertFalse(model.data["required"])

    def test_manual_start_is_available_in_both_modes_and_switching_preserves_progress(self):
        for school in (True, False):
            with self.subTest(school=school):
                model = Practice()
                env = {**DESKTOP, "school": school}
                model.advance(0, DAY, env)
                self.assertFalse(model.snapshot(0)["required"])
                self.assertTrue(model.start(DAY)["ok"])
                question = model.question()
                identifier = model.data["session"]
                self.assertTrue(model.snapshot(0)["show"])
                self.assertEqual(model.snapshot(0)["pause"], "")
                model.present(0, identifier, question["id"], True)
                model.advance(1, DAY, {**env, "school": not school})
                self.assertEqual(model.data["elapsed"], 1)
                self.assertEqual(model.question(), question)
                self.assertEqual(model.data["session"], identifier)
                self.assertTrue(model.answer(question["id"], str(question["a"] * question["b"]))["correct"])
                self.assertEqual(model.data["correct"], 1)
                restored = Practice(model.data)
                restored.advance(2, DAY, {**env, "school": True})
                self.assertTrue(restored.snapshot(2)["show"])
                self.assertEqual(restored.data, model.data)

    def test_school_practice_uses_the_same_round_duration_and_pass_score(self):
        self.env = {**DESKTOP, "school": True}
        self.practice.advance(0, DAY, self.env)
        self.answer_round(40)
        self.work(DURATION - 1)
        self.assertTrue(self.practice.data["required"])
        self.work(1)
        self.assertFalse(self.practice.data["required"])
        self.assertEqual(self.practice.data["result"], "complete")
        self.assertEqual(self.practice.data["last_round"]["correct"], 40)

    def test_legacy_queued_automatic_start_is_discarded_without_resetting_progress(self):
        saved = copy.deepcopy(self.practice.data)
        saved.update(activation_pending=True, login_session="old-login", elapsed=125,
                     answered=7, correct=6)
        model = Practice(saved)
        model.advance(0, DAY, DESKTOP)
        self.assertNotIn("activation_pending", model.data)
        self.assertNotIn("login_session", model.data)
        self.assertEqual(model.data["elapsed"], 125)
        self.assertEqual(model.data["answered"], 7)
        self.assertEqual(model.data["correct"], 6)
        self.assertEqual(model.question(), saved["question"])
        self.assertTrue(model.data["required"])
        for result in ("parent", "complete", ""):
            restored = Practice({**saved, "required": False, "result": result})
            restored.advance(1, "2026-09-13", {**DESKTOP, "session": "new-boot:login-one"})
            self.assertFalse(restored.data["required"])

    def test_upgrade_keeps_finished_days_but_starts_unscored_old_session_fresh(self):
        old = {"day": DAY, "required": True, "session": "old-session", "credited": 1234,
               "pending": 10, "correct": 42, "attempts": 70, "result": "", "deck": []}
        migrated = Practice(old)
        self.assertEqual(migrated.data["elapsed"], 0)
        self.assertEqual(migrated.data["answered"], 0)
        self.assertEqual(migrated.data["correct"], 0)
        self.assertTrue(migrated.data["required"])
        self.assertIn("fresh 50-question", migrated.data["migration_note"])
        for result in ("complete", "parent"):
            migrated = Practice({**old, "required": False, "result": result})
            migrated.advance(0, DAY, DESKTOP)
            self.assertFalse(migrated.data["required"])


if __name__ == "__main__":
    unittest.main()
