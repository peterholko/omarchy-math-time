import QtQuick
import Quickshell
import Quickshell.Wayland
import "MathModel.js" as Model

// The shell owns this overlay. Its independent service owns the questions,
// practice timer and parent authorization; closing a view never clears them.
Item {
  id: root
  property var shell: null
  property var manifest: null
  property var service: null
  property bool opened: false
  property bool parentOpen: false
  property string answer: ""
  property string feedback: ""
  property bool wrong: false
  property string parentNote: ""
  property string roundKey: ""
  readonly property var practiceService: service || (shell ? shell.serviceFor("io.github.peterholko.math") : null)
  readonly property var state: practiceService ? practiceService.state : ({required: false, remaining: 1800})
  readonly property bool connected: practiceService ? practiceService.connected : false
  readonly property bool busy: practiceService ? practiceService.busy : false
  readonly property bool parentBusy: practiceService ? practiceService.parentBusy : false
  readonly property bool covering: opened && (state.show === true || !state.required || !connected)

  function open(payloadJson) {
    if (!opened) { opened = true; parentOpen = false }
    updatePresence()
  }
  function close() {
    if (state.required && (state.show || !connected)) {
      parentOpen = true
      return "practice_required"
    }
    opened = false
    parentOpen = false
    updatePresence()
    return "ok"
  }
  function handleEscape() {
    if (busy) return
    if (parentOpen && !parentBusy) parentOpen = false
    else close()
  }
  function updatePresence() {
    if (practiceService) practiceService.setPresence(covering && state.required && !parentOpen)
  }
  function start() {
    if (practiceService) practiceService.request({cmd: "start"})
  }
  function submit() {
    if (busy || !connected || !state.question || !answer.trim()) return
    practiceService.request({cmd: "answer", question: state.question.id, answer: answer.trim()})
  }
  function endByParent(password) {
    if (!practiceService || busy) return
    parentNote = ""
    practiceService.request({cmd: "parent.end", password: password})
  }
  onStateChanged: {
    var key = String(state.session || "") + ":" + String(state.round || 1)
    if (key !== roundKey) {
      roundKey = key
      answer = ""
      feedback = ""
      wrong = false
    }
    if (state.required && !state.show && connected) opened = false
    updatePresence()
  }
  onCoveringChanged: updatePresence()
  onParentOpenChanged: { parentNote = ""; updatePresence() }
  Connections {
    target: root.practiceService
    function onReply(response) {
      if (response.action === "parent.end") {
        if (response.ok) { root.opened = false; root.parentOpen = false }
        else root.parentNote = Model.errorText(response.error)
      } else if (response.correct !== undefined) {
        root.wrong = !response.correct
        root.feedback = response.hint || (response.correct ? "Correct! Keep going." : "Keep going. You can learn this one.")
        root.answer = ""
      } else if (!response.ok) {
        root.wrong = true
        root.feedback = Model.errorText(response.error)
      }
    }
  }
  Variants {
    model: Quickshell.screens
    delegate: PanelWindow {
      id: practiceWindow
      required property var modelData
      screen: modelData
      visible: root.covering
      anchors { top: true; bottom: true; left: true; right: true }
      color: Model.PALETTE.paper
      WlrLayershell.namespace: "io.github.peterholko.math"
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
      exclusionMode: ExclusionMode.Ignore
      IdleInhibitor {
        window: practiceWindow
        enabled: root.covering && root.connected && root.state.required && !root.parentOpen
      }
      PracticeSheet { anchors.fill: parent; controller: root }
    }
  }
}
