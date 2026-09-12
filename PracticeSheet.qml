import QtQuick
import QtQuick.Controls.Basic
import qs.Commons
import "MathModel.js" as Model

Rectangle {
  id: sheet
  property var controller
  readonly property var state: controller.state
  readonly property bool practising: sheet.state.required === true
  readonly property bool finished: !practising && (sheet.state.result === "complete" || sheet.state.result === "parent")
  readonly property bool compact: height < 850
  readonly property string family: Style.font.family
  color: Model.PALETTE.paper
  focus: true
  Keys.onEscapePressed: controller.handleEscape()

  function focusInput() {
    if (!visible) return
    if (controller.parentOpen) password.forceActiveFocus()
    else if (practising) answerField.forceActiveFocus()
  }
  onVisibleChanged: if (visible) Qt.callLater(focusInput)
  Component.onCompleted: Qt.callLater(focusInput)
  Connections {
    target: sheet.controller
    function onParentOpenChanged() { password.text = ""; Qt.callLater(sheet.focusInput) }
    function onAnswerChanged() { Qt.callLater(sheet.focusInput) }
    function onBusyChanged() { if (!sheet.controller.busy) Qt.callLater(sheet.focusInput) }
  }

  component Action: Button {
    id: action
    implicitHeight: 48
    implicitWidth: Math.max(150, contentItem.implicitWidth + 44)
    leftPadding: 22
    rightPadding: 22
    font.family: sheet.family
    font.pixelSize: 18
    contentItem: Text {
      text: action.text
      textFormat: Text.PlainText
      color: action.enabled ? Model.PALETTE.mark : Model.PALETTE.inkSoft
      font: action.font
      horizontalAlignment: Text.AlignHCenter
      verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
      color: action.down ? "#e3ecff" : "#f1f5ff"
      radius: 10
      border.width: action.activeFocus ? 2 : 1
      border.color: action.enabled ? Model.PALETTE.mark : Model.PALETTE.rule
    }
  }

  Row {
    anchors { top: parent.top; left: parent.left; right: parent.right; margins: 28 }
    spacing: 16
    Text {
      width: parent.width - parentButton.width - parent.spacing
      text: "MATH TIME"
      color: Model.PALETTE.inkSoft
      font { family: sheet.family; pixelSize: 17; letterSpacing: 2 }
      height: parentButton.height
      verticalAlignment: Text.AlignVCenter
    }
    Action {
      id: parentButton
      text: controller.parentOpen ? "Back to practice" : practising ? "Esc · Parent" : "Close"
      enabled: !controller.parentBusy
      onClicked: controller.handleEscape()
    }
  }

  Flickable {
    anchors { top: parent.top; topMargin: 100; bottom: parent.bottom; bottomMargin: 24; left: parent.left; right: parent.right }
    contentHeight: Math.max(height, practiceColumn.height, parentColumn.height)
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar {}

  Column {
    id: practiceColumn
    width: Math.min(sheet.width - 48, 740)
    anchors.horizontalCenter: parent.horizontalCenter
    y: Math.max(0, (parent.height - height) / 2)
    spacing: sheet.compact ? 12 : 22
    visible: !controller.parentOpen
    Text {
      width: parent.width
      text: practising ? "Multiplication tables" : finished ? "Practice finished!" : "Make your tables second nature."
      textFormat: Text.PlainText
      color: Model.PALETTE.ink
      font { family: sheet.family; pixelSize: sheet.compact ? 30 : 40; bold: true }
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.WordWrap
    }
    Text {
      width: parent.width
      text: practising ? "Tables 1–12  ·  " + sheet.state.correct + " correct"
        : finished ? (sheet.state.result === "parent" ? "An adult ended this session." : "Thirty minutes of practice. Well done!")
        : "30 minutes of multiplication practice, one fact at a time."
      color: Model.PALETTE.inkSoft
      font { family: sheet.family; pixelSize: 18 }
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.WordWrap
    }
    Rectangle {
      visible: practising
      width: parent.width
      height: 7
      radius: 4
      color: "#eef0f5"
      Rectangle {
        width: parent.width * Math.max(0, Math.min(1, 1 - Number(sheet.state.remaining || 0) / 1800))
        height: parent.height
        radius: parent.radius
        color: Model.PALETTE.mark
      }
    }
    Text {
      objectName: "practiceCountdown"
      visible: practising
      width: parent.width
      text: Model.clock(sheet.state.remaining) + " of practice left"
      color: Model.PALETTE.inkSoft
      font { family: sheet.family; pixelSize: 19 }
      horizontalAlignment: Text.AlignHCenter
    }
    Text {
      objectName: "multiplicationQuestion"
      visible: practising
      width: parent.width
      text: sheet.state.question ? sheet.state.question.a + " × " + sheet.state.question.b + " = ?" : "Getting your question…"
      color: Model.PALETTE.ink
      font { family: sheet.family; pixelSize: sheet.compact ? 55 : 78; bold: true }
      horizontalAlignment: Text.AlignHCenter
    }
    TextField {
      id: answerField
      objectName: "answerField"
      visible: practising
      width: Math.min(parent.width, 260)
      height: sheet.compact ? 60 : 76
      anchors.horizontalCenter: parent.horizontalCenter
      text: controller.answer
      onTextEdited: controller.answer = text
      placeholderText: "Your answer"
      horizontalAlignment: TextInput.AlignHCenter
      font { family: sheet.family; pixelSize: 30 }
      maximumLength: 3
      validator: RegularExpressionValidator { regularExpression: /[0-9]{0,3}/ }
      enabled: controller.connected && !controller.busy
      selectByMouse: true
      color: Model.PALETTE.ink
      placeholderTextColor: Model.PALETTE.inkSoft
      background: Rectangle {
        color: "#fafbff"
        radius: 12
        border.width: 2
        border.color: answerField.activeFocus ? Model.PALETTE.mark : Model.PALETTE.rule
      }
      onAccepted: controller.submit()
      Keys.onEscapePressed: controller.handleEscape()
    }
    Action {
      anchors.horizontalCenter: parent.horizontalCenter
      text: controller.busy ? "Checking…" : practising ? "Check answer" : finished ? "Back to your desktop" : "Start 30-minute practice"
      enabled: !controller.busy && (finished || (controller.connected && sheet.state.active === true
        && sheet.state.school === false && (!practising || controller.answer.length > 0)))
      onClicked: {
        if (practising) controller.submit()
        else if (finished) controller.close()
        else controller.start()
      }
    }
    Text {
      objectName: "practiceFeedback"
      width: parent.width
      text: !controller.connected ? Model.errorText(controller.practiceService ? controller.practiceService.error : "service_unavailable")
        : sheet.state.remaining <= 0 && practising ? "One last correct answer to finish your practice!"
        : (sheet.state.pause || controller.feedback || (practising ? "Enter checks your answer. Take your time." : "Your progress is saved if you lock or restart."))
      textFormat: Text.PlainText
      color: controller.wrong ? Model.PALETTE.bad : Model.PALETTE.inkSoft
      font { family: sheet.family; pixelSize: 17 }
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.WordWrap
    }
  }

  Column {
    id: parentColumn
    visible: controller.parentOpen
    width: Math.min(sheet.width - 48, 600)
    anchors.horizontalCenter: parent.horizontalCenter
    y: Math.max(0, (parent.height - height) / 2)
    spacing: 22
    Text {
      width: parent.width
      text: "Parent"
      color: Model.PALETTE.ink
      font { family: sheet.family; pixelSize: 40; bold: true }
      horizontalAlignment: Text.AlignHCenter
    }
    Text {
      width: parent.width
      text: "Enter the parent password to end this practice session early."
      color: Model.PALETTE.inkSoft
      font { family: sheet.family; pixelSize: 19 }
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.WordWrap
    }
    TextField {
      id: password
      objectName: "parentPassword"
      width: parent.width
      height: 60
      font { family: sheet.family; pixelSize: 22 }
      echoMode: TextInput.Password
      maximumLength: 1024
      placeholderText: "Parent password"
      enabled: !controller.parentBusy
      color: Model.PALETTE.ink
      placeholderTextColor: Model.PALETTE.inkSoft
      background: Rectangle {
        radius: 10
        color: "#fafbff"
        border.width: 2
        border.color: password.activeFocus ? Model.PALETTE.mark : Model.PALETTE.rule
      }
      function submitPassword() {
        if (!text || controller.busy) return
        controller.endByParent(text)
        text = ""
      }
      onAccepted: submitPassword()
      Keys.onEscapePressed: controller.handleEscape()
    }
    Action {
      anchors.horizontalCenter: parent.horizontalCenter
      text: controller.parentBusy ? "Checking parent password…" : "End practice"
      enabled: !controller.busy && password.text.length > 0
      onClicked: password.submitPassword()
    }
    Text {
      width: parent.width
      text: controller.parentBusy ? "Checking the password. Please wait…" : controller.parentNote
      textFormat: Text.PlainText
      color: controller.parentBusy ? Model.PALETTE.inkSoft : Model.PALETTE.bad
      font { family: sheet.family; pixelSize: 17 }
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.WordWrap
    }
  }
  }
}
