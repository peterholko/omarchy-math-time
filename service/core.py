"""Multiplication practice policy. No desktop commands or screen-time imports."""
import copy
import secrets

DURATION = 30 * 60
QUESTION_LIMIT = 60
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
        self.data.setdefault("credited", 0.0)
        self.data.setdefault("pending", 0.0)
        self.data.setdefault("correct", 0)
        self.data.setdefault("attempts", 0)
        self.data.setdefault("streak", 0)
        self.data.setdefault("best_streak", 0)
        self.data.setdefault("deck", [])

    def usable(self):
        env = self.environment
        return (env.get("active") is True and env.get("locked") is False
                and env.get("school") is False)

    def begin(self, day):
        # Reopening an unfinished session cannot reset its timer or question.
        if self.data["required"]:
            return
        self.data.update(day=day, required=True, result="", credited=0.0, pending=0.0,
                         correct=0, attempts=0, streak=0, best_streak=0,
                         session=secrets.token_hex(16), question=None, deck=[])
        self.present_until = 0
        self.question()

    def question(self):
        if not self.data.get("question"):
            if not self.data["deck"]:
                deck = [[a, b] for a in range(1, 13) for b in range(1, 13)]
                secrets.SystemRandom().shuffle(deck)
                self.data["deck"] = deck
            a, b = self.data["deck"].pop()
            self.data["question"] = {"id": secrets.token_hex(16), "a": a, "b": b}
        return self.data["question"]

    def advance(self, now, day, environment):
        elapsed = max(0.0, min(2.0, now - self.last_tick)) if self.last_tick is not None else 0.0
        previous_usable = self.usable()
        previous_tick = self.last_tick
        self.last_tick = now
        self.environment = environment
        usable = self.usable()
        # Never credit a lock, suspend, missing display, or School Mode interval.
        if (self.data["required"] and usable and previous_usable and previous_tick is not None
                and self.present_until >= now):
            self.data["pending"] = min(QUESTION_LIMIT,
                DURATION - self.data["credited"], self.data["pending"] + elapsed)
        session = str(environment.get("session") or "")
        first_visit = not self.data["day"]
        new_day = day > self.data["day"]
        new_login = bool(session and session != self.data.get("login_session", ""))
        unlocked = environment.get("locked") is False and self.was_locked is True
        if new_day and self.trigger == "daily" and usable:
            self.data["required"] = False
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
        if (self.data["required"] and session == self.data.get("session")
                and question == self.question()["id"] and visible is True and self.usable()):
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
        if identifier != question["id"]:
            return {"ok": False, "error": "stale_question"}
        value = str(answer).strip()
        if not value.isascii() or not value.isdecimal() or len(value) > 3:
            return {"ok": False, "error": "use_digits"}
        self.data["attempts"] += 1
        if int(value) != question["a"] * question["b"]:
            self.data["streak"] = 0
            return {"ok": True, "correct": False, "hint": self.hint(question)}
        # Working time is only committed by a correct answer. Waiting at the
        # question for hours can contribute at most one minute, never a session.
        self.data["credited"] = min(DURATION, self.data["credited"] + self.data["pending"])
        self.data["pending"] = 0.0
        self.data["correct"] += 1
        self.data["streak"] += 1
        self.data["best_streak"] = max(self.data["best_streak"], self.data["streak"])
        self.data["question"] = None
        self.present_until = 0
        if self.data["credited"] >= DURATION:
            self.data["required"] = False
            self.data["result"] = "complete"
        else:
            self.question()
        return {"ok": True, "correct": True}

    @staticmethod
    def hint(question):
        a, b = question["a"], question["b"]
        if a == 1 or b == 1:
            return "One group keeps the other number the same."
        if a == 10 or b == 10:
            return "Ten groups: use place value to multiply by ten."
        if a == 2 or b == 2:
            return "The two-times table is doubles."
        return f"Think of {a} groups of {b}. Try a nearby table fact you know."

    def end_by_parent(self):
        self.data["required"] = False
        self.data["result"] = "parent"
        self.present_until = 0

    def snapshot(self, now):
        env = self.environment
        required = self.data["required"]
        question = self.question() if required else None
        if env.get("school") is True:
            pause = "School Mode is on. Practice will resume in Free Time."
        elif env.get("school") is None:
            pause = "Waiting for School Mode status."
        elif env.get("locked") is not False or env.get("active") is not True:
            pause = "Practice is paused while the desktop is locked or away."
        elif self.data["pending"] >= QUESTION_LIMIT:
            pause = "The timer is paused. Answer this question correctly to continue."
        else:
            pause = ""
        return {"ok": True, "version": 1, "required": required, "show": required and self.usable(),
                "session": self.data.get("session", ""), "question": question,
                "duration": DURATION, "remaining": max(0, DURATION - self.data["credited"] - self.data["pending"]),
                "credited": self.data["credited"], "pending": self.data["pending"],
                "correct": self.data["correct"], "attempts": self.data["attempts"],
                "streak": self.data["streak"], "best_streak": self.data["best_streak"],
                "result": self.data["result"], "pause": pause, "trigger": self.trigger,
                "school": env.get("school"), "locked": env.get("locked", True),
                "active": env.get("active", False), "day": self.data["day"]}
