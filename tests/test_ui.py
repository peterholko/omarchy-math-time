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
from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject, QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[1]
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
    property var state: ({required:true, show:true, active:true, locked:false, school:false,
      question:{id:"one", a:7, b:8}, session:"session", remaining:1800, credited:0, pending:0, correct:0})
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
      service.state = Object.assign({}, service.state, {show:false, school:true})
    } else if(action === "free") {
      service.state = Object.assign({}, service.state, {show:true, school:false})
      math.open("{}")
    } else if(action === "offline") service.connected = false
    else if(action === "complete") {
      service.state = Object.assign({}, service.state, {required:false, show:false, result:"complete", remaining:0, correct:300})
    } else if(action === "close") math.close()
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

    def test_visible_question_and_timer_use_practice_state(self):
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
        question = find(window.contentItem(), "multiplicationQuestion")
        countdown = find(window.contentItem(), "practiceCountdown")
        self.assertEqual(question.property("text"), "7 × 8 = ?")
        self.assertEqual(countdown.property("text"), "30:00 of practice left")

    def test_answers_reach_verifier_and_cannot_dismiss_an_active_session(self):
        state = self.step("answer")
        self.assertEqual(state["request"], {"cmd": "answer", "question": "one", "answer": "56"})
        self.assertFalse(self.step("escape")["parentOpen"])
        state = self.step("correct")
        self.assertEqual(state["answer"], "")
        self.assertTrue(state["opened"])

    def test_parent_feedback_and_successful_early_exit(self):
        self.step("escape")
        self.assertTrue(self.step("parent")["parentBusy"])
        state = self.step("bad-password")
        self.assertTrue(state["opened"])
        self.assertIn("wasn't accepted", state["parentNote"])
        self.step("parent")
        self.assertFalse(self.step("parent-ok")["opened"])

    def test_school_pauses_overlay_and_free_time_resumes_it(self):
        self.assertFalse(self.step("school")["covering"])
        self.assertFalse(self.step("inspect")["present"])
        self.assertTrue(self.step("free")["covering"])

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
