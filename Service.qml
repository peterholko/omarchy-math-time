import QtQuick
import Quickshell
import Quickshell.Io

Item {
  id: root
  property var shell: null
  property var manifest: null
  property var state: ({required: false, show: false, remaining: 1800})
  property bool connected: false
  property string error: ""
  property bool busy: false
  property bool parentBusy: false
  property string pendingRequest: ""
  property string requestKind: ""
  property string presence: '{"visible":false}'
  readonly property string client: decodeURIComponent(Qt.resolvedUrl("client.py").toString().replace(/^file:\/\//, ""))
  signal reply(var response)

  function apply(response) {
    if (response && response.ok === true) {
      connected = true
      error = ""
      state = response
      if (state.show && shell) shell.summon("io.github.peterholko.math", '{"resume":true}')
      else if (state.required && shell) shell.hide("io.github.peterholko.math")
    } else {
      connected = false
      error = String(response && response.error || "service_unavailable")
      if (error === "not_enrolled") state = ({required: false, show: false, remaining: 1800})
    }
  }

  function setPresence(visible) {
    var value = JSON.stringify({visible: visible === true, session: state.session || "",
      question: state.question ? state.question.id : ""})
    if (value === presence) return
    presence = value
    if (watch.running) watch.write(presence + "\n")
  }

  function request(message) {
    if (busy) return false
    busy = true
    requestKind = message.cmd
    parentBusy = message.cmd === "parent.end"
    pendingRequest = JSON.stringify(message) + "\n"
    requestTimeout.restart()
    control.launched = false
    control.running = true
    return true
  }

  function finish(raw) {
    if (!busy) return
    requestTimeout.stop()
    busy = false
    parentBusy = false
    pendingRequest = ""
    var kind = requestKind
    requestKind = ""
    var response
    try { response = JSON.parse(raw) } catch (e) { response = {ok: false, error: "service_unavailable"} }
    response.action = kind
    if (response.state) apply(response.state)
    reply(response)
  }

  Process {
    id: watch
    command: ["python3", "-I", root.client, "watch"]
    stdinEnabled: true
    onStarted: write(root.presence + "\n")
    stdout: SplitParser {
      onRead: function(data) {
        try { root.apply(JSON.parse(data)) } catch (e) {
          root.connected = false
          root.error = "service_unavailable"
        }
      }
    }
    onExited: {
      root.connected = false
      root.error = "service_unavailable"
    }
  }
  Process {
    id: control
    property bool launched: false
    command: ["python3", "-I", root.client, "request"]
    stdinEnabled: true
    onStarted: {
      launched = true
      write(root.pendingRequest)
      root.pendingRequest = ""
    }
    stdout: StdioCollector { id: result; waitForEnd: true }
    onExited: root.finish(result.text)
    onRunningChanged: if (!running && !launched && root.busy) root.finish("")
  }
  Timer {
    id: requestTimeout
    interval: 30000
    onTriggered: { control.running = false; root.finish("") }
  }
  Timer {
    interval: 2000
    repeat: true
    triggeredOnStart: true
    running: true
    onTriggered: if (!watch.running) watch.running = true
  }
}
