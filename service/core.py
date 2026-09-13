"""Multiplication rounds with server-owned timing and first-answer scoring."""
import copy
import secrets

POLICY_VERSION = 2
DURATION = 30 * 60
RETRY_DURATION = 15 * 60
QUESTION_COUNT = 50
RETRY_QUESTION_COUNT = 25
PASS_SCORE = 40
RETRY_PASS_SCORE = 20
TRIGGERS = ("daily", "unlock", "manual")


class Practice:
    def __init__(self, saved=None, trigger="daily"):
        self.data = copy.deepcopy(saved or {})
        self.trigger = trigger
        self.last_tick = None
        self.present_until = 0
        self.environment = {}
        self.was_locked = None
        self.data.setdefault("day", "")
        self.data.setdefault("required", False)
        self.data.setdefault("result", "")
        self.data.setdefault("session", "")
        self.data.setdefault("deck", [])
        if self.data.get("policy_version") != POLICY_VERSION:
            # Version 1 counted corrected answers, so its first-answer score
            # cannot be reconstructed. Keep completed days; restart only an
            # unfinished old session under the new, shorter question quota.
            self.data.update(policy_version=POLICY_VERSION, round=1, elapsed=0.0,
                             answered=0, correct=0, attempts=0, total_correct=0,
                             streak=0, best_streak=0, last_round=None, question=None)
            self.data.pop("credited", None)
            self.data.pop("pending", None)
            if saved and self.data["required"]:
                self.data["migration_note"] = "Updated practice: a fresh 50-question round starts now."
        self.data.setdefault("migration_note", "")

    @property
    def duration(self):
        return DURATION if self.data["round"] == 1 else RETRY_DURATION

    @property
    def question_count(self):
        return QUESTION_COUNT if self.data["round"] == 1 else RETRY_QUESTION_COUNT

    @property
    def pass_score(self):
        return PASS_SCORE if self.data["round"] == 1 else RETRY_PASS_SCORE

    def usable(self):
        env = self.environment
        return (env.get("active") is True and env.get("locked") is False
                and env.get("school") is False)

    def begin(self, day):
        # Reopening an unfinished session cannot reset its timer or score.
        if self.data["required"]:
            return
        self.data.update(day=day, required=True, result="", round=1, elapsed=0.0,
                         answered=0, correct=0, attempts=0, total_correct=0,
                         streak=0, best_streak=0, last_round=None, migration_note="",
                         session=secrets.token_hex(16), question=None, deck=[])
        self.present_until = 0
        self.question()

    def question(self):
        if not self.data["required"] or self.data["answered"] >= self.question_count:
            return None
        if not self.data.get("question"):
            if not self.data["deck"]:
                deck = [[a, b] for a in range(1, 13) for b in range(1, 13)]
                secrets.SystemRandom().shuffle(deck)
                self.data["deck"] = deck
            a, b = self.data["deck"].pop()
            self.data["question"] = {"id": secrets.token_hex(16), "a": a, "b": b}
        return self.data["question"]

    def finish_round(self):
        passed = self.data["correct"] >= self.pass_score
        self.data["last_round"] = {"number": self.data["round"], "duration": self.duration,
            "questions": self.question_count, "target": self.pass_score,
            "answered": self.data["answered"], "correct": self.data["correct"], "passed": passed}
        self.data["question"] = None
        self.present_until = 0
        if passed:
            self.data["required"] = False
            self.data["result"] = "complete"
        else:
            # Every retry has its own 25 questions, 20-answer target and timer.
            # A previous round's points cannot pass the next one.
            self.data.update(round=self.data["round"] + 1, elapsed=0.0,
                             answered=0, correct=0, streak=0, migration_note="")
            self.question()
        return passed

    def advance(self, now, day, environment):
        now = max(now, self.last_tick) if self.last_tick is not None else now
        elapsed = max(0.0, min(2.0, now - self.last_tick)) if self.last_tick is not None else 0.0
        previous_usable = self.usable()
        previous_tick = self.last_tick
        self.last_tick = now
        self.environment = environment
        usable = self.usable()
        # Never count a lock, suspend, missing view, or School Mode interval.
        if (self.data["required"] and usable and previous_usable and previous_tick is not None
                and self.present_until >= now):
            self.data["elapsed"] = min(self.duration, self.data["elapsed"] + elapsed)
            if self.data["elapsed"] >= self.duration:
                if self.finish_round():
                    # Finishing an overnight session also satisfies the day
                    # it ends, rather than immediately starting another one.
                    self.data["day"] = max(day, self.data["day"])
        session = str(environment.get("session") or "")
        first_visit = not self.data["day"]
        new_day = day > self.data["day"]
        new_login = bool(session and session != self.data.get("login_session", ""))
        unlocked = environment.get("locked") is False and self.was_locked is True
        if self.trigger == "unlock" and (first_visit or new_login or unlocked):
            self.data["activation_pending"] = True
        due = (self.trigger == "daily" and (first_visit or new_day)) or (
            self.trigger == "unlock" and self.data.get("activation_pending", False))
        if due and usable and not self.data["required"]:
            self.begin(day)
        if due and usable:
            self.data["activation_pending"] = False
        if session:
            self.data["login_session"] = session
        self.was_locked = environment.get("locked")

    def present(self, now, session, question, visible):
        current = self.question()
        identifier = current["id"] if current else ""
        if (self.data["required"] and session == self.data["session"]
                and question == identifier and visible is True and self.usable()):
            self.present_until = now + 3
        else:
            self.present_until = 0

    def start(self, day):
        if not self.usable():
            return {"ok": False, "error": "school_or_locked"}
        if self.trigger == "daily" and self.data["day"] >= day and not self.data["required"]:
            return {"ok": False, "error": "finished_today"}
        self.begin(day)
        return {"ok": True}

    def answer(self, identifier, answer):
        if not self.data["required"] or not self.usable():
            return {"ok": False, "error": "not_practising"}
        question = self.question()
        if question is None or identifier != question["id"]:
            return {"ok": False, "error": "stale_question"}
        value = str(answer).strip()
        if not value.isascii() or not value.isdecimal() or len(value) > 3:
            return {"ok": False, "error": "use_digits"}
        correct = int(value) == question["a"] * question["b"]
        self.data["attempts"] += 1
        self.data["answered"] += 1
        if correct:
            self.data["correct"] += 1
            self.data["total_correct"] += 1
            self.data["streak"] += 1
            self.data["best_streak"] = max(self.data["best_streak"], self.data["streak"])
        else:
            self.data["streak"] = 0
        # Both right and wrong submissions consume the question exactly once.
        # Replays/retries cannot turn an incorrect first answer into a point.
        self.data["question"] = None
        self.present_until = 0
        self.question()
        fact = f"{question['a']} × {question['b']} = {question['a'] * question['b']}"
        return {"ok": True, "correct": correct,
                "hint": "Correct! " + fact if correct else "Let's remember: " + fact}

    def end_by_parent(self, day=None):
        self.data["required"] = False
        self.data["result"] = "parent"
        if day is not None:
            self.data["day"] = max(day, self.data["day"])
        self.present_until = 0

    def snapshot(self, now):
        env = self.environment
        required = self.data["required"]
        if env.get("school") is True:
            pause = "School Mode is on. Practice will resume in Free Time."
        elif env.get("school") is None:
            pause = "Waiting for School Mode status."
        elif env.get("locked") is not False or env.get("active") is not True:
            pause = "Practice is paused while the desktop is locked or away."
        else:
            pause = ""
        return {"ok": True, "version": POLICY_VERSION, "required": required,
                "show": required and self.usable(), "session": self.data["session"],
                "question": self.question(), "round": self.data["round"],
                "question_count": self.question_count, "target": self.pass_score,
                "duration": self.duration, "remaining": max(0, self.duration - self.data["elapsed"]),
                "elapsed": self.data["elapsed"], "answered": self.data["answered"],
                "correct": self.data["correct"], "attempts": self.data["attempts"],
                "total_correct": self.data["total_correct"], "last_round": self.data["last_round"],
                "streak": self.data["streak"], "best_streak": self.data["best_streak"],
                "migration_note": self.data["migration_note"], "result": self.data["result"],
                "pause": pause, "trigger": self.trigger, "school": env.get("school"),
                "locked": env.get("locked", True), "active": env.get("active", False), "day": self.data["day"]}
