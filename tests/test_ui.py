"""Actual QML controller and view, with a Qt window adapter for portable QA."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject, QObject, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "service"))
from core import Practice
APP = QGuiApplication.instance() or QGuiApplication([])


class UiTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

        def write(name, content):
            path = self.base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        for name in ("PracticeSheet.qml", "MathModel.js"):
            shutil.copyfile(ROOT / name, self.base / name)
        qml = (ROOT / "MathTime.qml").read_text()
        qml = "\n".join(line for line in qml.splitlines() if "WlrLayershell." not in line and "exclusionMode:" not in line)
        qml = qml.replace("      anchors { top: true; bottom: true; left: true; right: true }", "      width: 1100; height: 780")
        write("MathTime.qml", qml)
        write("qml/Quickshell/qmldir", "module Quickshell\nsingleton Quickshell 1.0 Quickshell.qml\nVariants 1.0 Variants.qml\nPanelWindow 1.0 PanelWindow.qml\n")
        write("qml/Quickshell/Quickshell.qml", 'pragma Singleton\nimport QtQuick\nQtObject { property var screens: [null] }\n')
        write("qml/Quickshell/Variants.qml", 'import QtQml.Models\nInstantiator {}\n')
        write("qml/Quickshell/PanelWindow.qml", 'import QtQuick\nWindow {}\n')
        write("qml/Quickshell/Wayland/qmldir", "module Quickshell.Wayland\nIdleInhibitor 1.0 IdleInhibitor.qml\n")
        write("qml/Quickshell/Wayland/IdleInhibitor.qml", "import QtQuick\nQtObject { property var window; property bool enabled }\n")
        write("qml/qs/Commons/qmldir", "module qs.Commons\nsingleton Style 1.0 Style.qml\n")
        write("qml/qs/Commons/Style.qml", 'pragma Singleton\nimport QtQuick\nQtObject { property var font: ({family:' + json.dumps("Helvetica" if sys.platform == "darwin" else "DejaVu Sans") + '}) }\n')
        write("Probe.qml", '''
import QtQuick
Item {
  id: probe
  property QtObject service: QtObject {
    property var state: ({version:4, trigger:"manual", required:true, show:true, active:true, locked:false, school:false,
      round:1, question_count:50, target:40, answered:0, duration:1800, elapsed:0, last_round:null,
      question:{id:"one", a:7, b:8, stage:"first"}, session:"session", remaining:1800, correct:0})
    property bool connected: true
    property bool busy: false
    property bool parentBusy: false
    property string error: ""
    property var requestValue: ({})
    property bool present: false
    signal reply(var response)
    function setPresence(value) { present = value }
    function request(value) { requestValue = value; busy = true; parentBusy = value.cmd === "parent.end" }
  }
  MathTime { id: math; service: probe.service }
  function setState(raw: string) {
    service.busy = false
    service.state = JSON.parse(raw)
  }
  function step(action: string): string {
    if(action === "open") math.open("{}")
    else if(action === "escape") math.handleEscape()
    else if(action === "answer") { math.answer = "56"; math.submit() }
    else if(action === "correct") {
      service.busy = false
      service.reply({ok:true, correct:true, action:"answer"})
    } else if(action === "parent") math.endByParent("example-parent-password")
    else if(action === "bad-password") {
      service.busy = false; service.parentBusy = false
      service.reply({ok:false, error:"bad_password", action:"parent.end"})
    } else if(action === "parent-ok") {
      service.busy = false; service.parentBusy = false
      service.state = Object.assign({}, service.state, {required:false, show:false, result:"parent"})
      service.reply({ok:true, action:"parent.end"})
    } else if(action === "school") {
      service.state = Object.assign({}, service.state, {show:service.state.required, school:true})
    } else if(action === "free") {
      service.state = Object.assign({}, service.state, {show:service.state.required, school:false})
    } else if(action === "unknown-school") {
      service.state = Object.assign({}, service.state, {show:false, school:null})
    } else if(action === "idle") {
      service.busy = false; service.connected = true
      service.state = Object.assign({}, service.state, {required:false, show:false, result:"", question:null,
        school:false, locked:false, active:true})
      service.requestValue = ({})
    } else if(action === "locked") {
      service.state = Object.assign({}, service.state, {show:false, locked:true})
    } else if(action === "unlocked") {
      service.state = Object.assign({}, service.state, {show:service.state.required, locked:false})
    } else if(action === "offline") service.connected = false
    else if(action === "complete") {
      service.state = Object.assign({}, service.state, {required:false, show:false, result:"complete", remaining:0, answered:50, correct:40, last_round:{questions:50, correct:40, passed:true}})
    } else if(action === "waiting") {
      service.state = Object.assign({}, service.state, {answered:50, correct:40, question:null, remaining:120})
    } else if(action === "waiting-fail") {
      service.state = Object.assign({}, service.state, {answered:50, correct:39, question:null, remaining:120})
    } else if(action === "retry") {
      math.answer = "56"
      service.state = Object.assign({}, service.state, {round:2, question_count:25, target:20,
        answered:0, correct:0, duration:900, remaining:900, question:{id:"retry-one", a:6, b:9},
        last_round:{number:1, questions:50, target:40, correct:39, passed:false}})
    } else if(action === "guided") {
      service.busy = false
      service.state = Object.assign({}, service.state, {answered:1, correct:0,
        question:{id:"guided-one", a:7, b:8, stage:"retry", hint:"Not quite. Work out 7 × 4, then double it."}})
    } else if(action === "guided-last") {
      service.state = Object.assign({}, service.state, {answered:50, correct:39,
        question:{id:"guided-last", a:7, b:8, stage:"retry", hint:"Not quite. Work out 7 × 4, then double it."}})
    } else if(action === "reveal") {
      service.busy = false
      service.state = Object.assign({}, service.state, {answered:1, correct:0,
        question:{id:"revealed-one", a:7, b:8, stage:"reveal", solution:56}})
    } else if(action === "retry-correct" || action === "acknowledged") {
      service.busy = false
      service.state = Object.assign({}, service.state, {answered:1, correct:0,
        question:{id:"next-one", a:6, b:6, stage:"first"}})
      service.reply(action === "acknowledged" ? {ok:true, acknowledged:true, action:"acknowledge"}
        : {ok:true, correct:true, scored:false, action:"answer", hint:"That's it! 7 × 8 = 56. Your first-answer score stays the same."})
    } else if(action === "acknowledge") math.acknowledge()
    else if(action === "close") math.close()
    return JSON.stringify({opened:math.opened, covering:math.covering, parentOpen:math.parentOpen,
      answer:math.answer, present:service.present, feedback:math.feedback, parentNote:math.parentNote,
      request:service.requestValue, busy:service.busy, parentBusy:service.parentBusy})
  }
}
''')
        self.engine = QQmlEngine()
        self.engine.addImportPath(str(self.base / "qml"))
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(self.base / "Probe.qml")))
        self.assertEqual(self.component.status(), QQmlComponent.Ready, str(self.component.errors()))
        self.probe = self.component.create()
        self.assertIsNotNone(self.probe)
        self.addCleanup(self.dispose)
        QTest.qWait(60)
        self.step("open")

    def dispose(self):
        self.probe.deleteLater()
        self.engine.deleteLater()
        QTest.qWait(20)

    def step(self, action):
        value = QMetaObject.invokeMethod(self.probe, "step", Q_RETURN_ARG(str), Q_ARG(str, action))
        QTest.qWait(10)
        return json.loads(value)

    def test_escape_requires_parent_and_pauses_presence(self):
        self.assertTrue(self.step("inspect")["present"])
        state = self.step("escape")
        self.assertTrue(state["opened"])
        self.assertTrue(state["parentOpen"])
        self.assertFalse(state["present"])
        self.assertTrue(self.step("escape")["present"])

    def view(self, name):
        from PySide6.QtQuick import QQuickWindow
        window = next(window for window in APP.allWindows() if isinstance(window, QQuickWindow))
        def find(item, name):
            if item.objectName() == name:
                return item
            for child in item.childItems():
                found = find(child, name)
                if found is not None:
                    return found
            return None
        return find(window.contentItem(), name)

    def test_visible_question_and_timer_use_practice_state(self):
        self.assertEqual(self.view("multiplicationQuestion").property("text"), "7 × 8 = ?")
        self.assertEqual(self.view("practiceCountdown").property("text"), "30:00 left in this round")

    def test_finished_questions_wait_for_deadline_without_asking_more(self):
        state = self.step("waiting")
        self.assertTrue(state["opened"])
        self.assertTrue(state["present"])
        self.assertEqual(self.view("multiplicationQuestion").property("text"), "All 50 answered")
        self.assertFalse(self.view("answerField").property("visible"))
        self.assertIn("timer ends", self.view("roundGuidance").property("text"))

    def test_follow_up_round_resets_input_and_displays_25_question_target(self):
        state = self.step("retry")
        self.assertEqual(state["answer"], "")
        self.assertEqual(self.view("multiplicationQuestion").property("text"), "6 × 9 = ?")
        self.assertEqual(self.view("practiceCountdown").property("text"), "15:00 left in this round")
        self.assertIn("0/25 answered", self.view("roundScore").property("text"))
        self.assertIn("Goal: 20", self.view("roundScore").property("text"))
        self.assertIn("39/50", self.view("roundGuidance").property("text"))

    def test_result_screen_shows_the_passed_round_score(self):
        self.step("complete")
        self.assertIn("40/50 correct", self.view("roundScore").property("text"))

    def test_answers_reach_verifier_and_cannot_dismiss_an_active_session(self):
        state = self.step("answer")
        self.assertEqual(state["request"], {"cmd": "answer", "question": "one", "answer": "56"})
        self.assertFalse(self.step("escape")["parentOpen"])
        state = self.step("correct")
        self.assertEqual(state["answer"], "")
        self.assertTrue(state["opened"])

    def test_guided_retry_keeps_question_hides_answer_and_preserves_score(self):
        self.step("guided")
        self.assertEqual(self.view("multiplicationQuestion").property("text"), "7 × 8 = ?")
        self.assertIn("7 × 4", self.view("questionHelp").property("text"))
        self.assertNotIn("56", self.view("questionHelp").property("text"))
        self.assertEqual(self.view("practiceAction").property("text"), "Check retry")
        self.assertTrue(self.view("answerField").property("visible"))
        self.assertEqual(self.step("answer")["request"]["question"], "guided-one")
        self.step("retry-correct")
        self.assertEqual(self.view("multiplicationQuestion").property("text"), "6 × 6 = ?")
        self.assertIn("1/50 answered", self.view("roundScore").property("text"))
        self.assertIn("0 correct", self.view("roundScore").property("text"))

    def test_revealed_answer_waits_for_continue_and_enter_acknowledges(self):
        from PySide6.QtQuick import QQuickWindow
        self.step("reveal")
        self.assertEqual(self.view("multiplicationQuestion").property("text"), "7 × 8 = 56")
        self.assertFalse(self.view("answerField").property("visible"))
        self.assertEqual(self.view("practiceAction").property("text"), "Continue")
        self.assertTrue(self.view("practiceAction").property("enabled"))
        self.assertEqual(self.step("inspect")["request"], {})
        window = next(window for window in APP.allWindows() if isinstance(window, QQuickWindow))
        QTest.keyClick(window, Qt.Key_Return)
        state = self.step("inspect")
        self.assertEqual(state["request"], {"cmd": "acknowledge", "question": "revealed-one"})
        self.step("acknowledged")
        self.assertEqual(self.view("multiplicationQuestion").property("text"), "6 × 6 = ?")
        self.assertTrue(self.view("answerField").property("visible"))

    def test_final_scored_question_still_shows_its_retry(self):
        self.step("guided-last")
        self.assertEqual(self.view("multiplicationQuestion").property("text"), "7 × 8 = ?")
        self.assertTrue(self.view("answerField").property("visible"))
        self.assertEqual(self.view("practiceAction").property("text"), "Check retry")
        self.assertIn("50/50 answered", self.view("roundScore").property("text"))

    def test_continue_cannot_skip_an_unanswered_question(self):
        self.assertEqual(self.step("acknowledge")["request"], {})

    def test_parent_feedback_and_successful_early_exit(self):
        self.step("escape")
        self.assertTrue(self.step("parent")["parentBusy"])
        state = self.step("bad-password")
        self.assertTrue(state["opened"])
        self.assertIn("wasn't accepted", state["parentNote"])
        self.step("parent")
        self.assertFalse(self.step("parent-ok")["opened"])

    def test_school_and_free_time_keep_the_current_practice_open(self):
        for action in ("school", "free"):
            self.assertTrue(self.step(action)["covering"])
            self.assertTrue(self.step("inspect")["present"])
        self.step("school")
        self.assertEqual(self.step("answer")["request"]["cmd"], "answer")

    def test_lock_still_pauses_practice_and_requires_manual_reopening(self):
        self.step("school")
        self.assertFalse(self.step("locked")["covering"])
        self.assertFalse(self.step("inspect")["present"])
        self.assertFalse(self.step("unlocked")["covering"])
        self.assertTrue(self.step("open")["covering"])

    def activate_main_action(self):
        self.assertTrue(QMetaObject.invokeMethod(self.view("practiceAction"), "activate"))
        return self.step("inspect")

    def test_opening_idle_app_waits_for_explicit_start(self):
        self.step("idle")
        self.step("close")
        self.assertEqual(self.step("open")["request"], {})
        self.assertEqual(self.view("practiceAction").property("text"), "Start 50-question round")
        self.assertEqual(self.activate_main_action()["request"], {"cmd": "start"})

    def test_finished_and_parent_ended_sessions_offer_another_manual_start(self):
        for result in ("parent-ok", "complete"):
            with self.subTest(result=result):
                self.step(result)
                self.step("open")
                self.assertEqual(self.view("practiceAction").property("text"), "Start another session")
                state = self.activate_main_action()
                self.assertEqual(state["request"], {"cmd": "start"})
                self.assertTrue(state["opened"])
                self.step("correct")

    def test_manual_start_button_works_in_school_and_free_time(self):
        for action in ("school", "free"):
            with self.subTest(action=action):
                self.step("idle")
                self.step(action)
                self.step("open")
                self.assertTrue(self.view("practiceAction").property("enabled"))
                self.assertEqual(self.activate_main_action()["request"], {"cmd": "start"})

    def apply_service_state(self, state):
        self.assertTrue(QMetaObject.invokeMethod(self.probe, "setState", Q_ARG(str, json.dumps(state))))
        QTest.qWait(10)

    def test_manual_school_start_uses_real_service_state_and_counts_practice(self):
        model = Practice()
        environment = {"active": True, "locked": False, "school": True}
        model.advance(0, "2026-09-16", environment)
        self.apply_service_state(model.snapshot(0))
        self.assertEqual(self.step("inspect")["request"], {})
        self.assertEqual(self.activate_main_action()["request"], {"cmd": "start"})
        self.assertTrue(model.start("2026-09-16")["ok"])
        self.apply_service_state(model.snapshot(0))
        self.assertTrue(self.step("inspect")["covering"])
        self.assertTrue(self.step("inspect")["present"])
        self.assertEqual(self.view("practiceAction").property("text"), "Check answer")
        model.present(0, model.data["session"], model.question()["id"], True)
        model.advance(1, "2026-09-16", environment)
        self.apply_service_state(model.snapshot(1))
        self.assertEqual(model.data["elapsed"], 1)
        self.assertTrue(self.step("inspect")["covering"])

    def test_manual_start_button_requires_available_unlocked_desktop(self):
        for action in ("unknown-school", "locked", "offline"):
            with self.subTest(action=action):
                self.step("idle")
                self.step(action)
                self.assertFalse(self.view("practiceAction").property("enabled"))
                self.assertEqual(self.activate_main_action()["request"], {})

    def test_connection_failure_does_not_release_required_practice(self):
        self.step("offline")
        state = self.step("close")
        self.assertTrue(state["covering"])
        self.assertTrue(state["parentOpen"])

    def test_completed_practice_can_be_closed(self):
        self.step("complete")
        self.assertFalse(self.step("close")["opened"])


if __name__ == "__main__":
    unittest.main()
