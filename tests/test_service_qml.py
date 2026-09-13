"""Compile and exercise the actual service QML with controlled process I/O."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest
from test_ui import APP, ROOT


class ServiceQmlTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)

        def write(name, data):
            path = base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data)
        shutil.copyfile(ROOT / "Service.qml", base / "Service.qml")
        write("qml/Quickshell/qmldir", "module Quickshell\nsingleton Quickshell 1.0 Quickshell.qml\n")
        write("qml/Quickshell/Quickshell.qml", "pragma Singleton\nimport QtQuick\nQtObject { property var processes: [] }\n")
        write("qml/Quickshell/Io/qmldir", "module Quickshell.Io\nProcess 1.0 Process.qml\nSplitParser 1.0 SplitParser.qml\nStdioCollector 1.0 StdioCollector.qml\n")
        write("qml/Quickshell/Io/Process.qml", '''
import QtQuick
import Quickshell
QtObject {
  id: root
  property var command: []
  property var stdout
  property bool stdinEnabled: false
  property bool running: false
  property var writes: []
  signal started()
  signal exited(int code)
  function write(value) { writes = writes.concat([value]) }
  onRunningChanged: if (running) Qt.callLater(function() { root.started() })
  Component.onCompleted: Quickshell.processes = Quickshell.processes.concat([root])
}
''')
        write("qml/Quickshell/Io/SplitParser.qml", "import QtQuick\nQtObject { signal read(string data) }\n")
        write("qml/Quickshell/Io/StdioCollector.qml", 'import QtQuick\nQtObject { property string text: ""; property bool waitForEnd: false }\n')
        write("Probe.qml", '''
import QtQuick
import Quickshell
Item {
  id: probe
  property var summons: []
  property var hides: []
  property var response: ({})
  function summon(id, payload) { summons = summons.concat([id]) }
  function hide(id) { hides = hides.concat([id]) }
  Service { id: service; shell: probe; onReply: value => probe.response = value }
  function step(action: string): string {
    var watch = Quickshell.processes.find(p => p.command[3] === "watch")
    var control = Quickshell.processes.find(p => p.command[3] === "request")
    if (action === "status") watch.stdout.read(JSON.stringify({ok:true, version:2, required:true, show:true,
      session:"session", question:{id:"question", a:7, b:8}, remaining:1800}))
    else if (action === "old-service") watch.stdout.read('{"ok":true,"version":1,"required":true}')
    else if (action === "present") service.setPresence(true)
    else if (action === "school") watch.stdout.read(JSON.stringify({ok:true, version:2, required:true, show:false, school:true}))
    else if (action === "offline") watch.stdout.read('{"ok":false,"error":"service_unavailable"}')
    else if (action === "request") service.request({cmd:"parent.end", password:"example-password"})
    else if (action === "reply") { control.stdout.text = '{"ok":false,"error":"bad_password"}'; control.running = false; control.exited(0) }
    return JSON.stringify({summons:summons, hides:hides, state:service.state, connected:service.connected, error:service.error,
      busy:service.busy, parentBusy:service.parentBusy, writes:watch.writes, requests:control.writes,
      command:control.command, pending:service.pendingRequest, response:response})
  }
}
''')
        self.engine = QQmlEngine()
        self.engine.addImportPath(str(base / "qml"))
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(base / "Probe.qml")))
        self.assertEqual(self.component.status(), QQmlComponent.Ready, str(self.component.errors()))
        self.probe = self.component.create()
        self.assertIsNotNone(self.probe)
        self.addCleanup(self.dispose)
        QTest.qWait(60)

    def dispose(self):
        self.probe.deleteLater()
        self.engine.deleteLater()
        QTest.qWait(20)

    def step(self, action):
        value = QMetaObject.invokeMethod(self.probe, "step", Q_RETURN_ARG(str), Q_ARG(str, action))
        QTest.qWait(10)
        return json.loads(value)

    def test_status_reopens_practice_and_school_hides_it(self):
        self.assertEqual(self.step("status")["summons"], ["io.github.peterholko.math"])
        self.assertEqual(self.step("school")["hides"], ["io.github.peterholko.math"])

    def test_presence_is_deduplicated_to_avoid_a_feedback_loop(self):
        self.step("status")
        first = self.step("present")
        second = self.step("present")
        self.assertEqual(first["writes"], second["writes"])
        self.assertEqual(json.loads(first["writes"][-1]), {"visible": True, "session": "session", "question": "question"})

    def test_password_travels_on_stdin_and_reply_preserves_its_action(self):
        self.step("request")
        waiting = self.step("inspect")
        self.assertTrue(waiting["parentBusy"])
        self.assertNotIn("example-password", str(waiting["command"]))
        self.assertEqual(waiting["pending"], "")
        self.assertEqual(json.loads(waiting["requests"][0])["password"], "example-password")
        result = self.step("reply")
        self.assertFalse(result["busy"])
        self.assertEqual(result["response"]["action"], "parent.end")
        self.assertEqual(result["response"]["error"], "bad_password")

    def test_outage_preserves_last_required_session(self):
        self.step("status")
        status = self.step("offline")
        self.assertFalse(status["connected"])
        self.assertTrue(status["state"]["required"])

    def test_old_service_needs_an_explicit_upgrade(self):
        status = self.step("old-service")
        self.assertFalse(status["connected"])
        self.assertEqual(status["error"], "upgrade_required")
