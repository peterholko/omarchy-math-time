import QtQuick
import QtQuick.Controls.Basic
import qs.Commons
import "MathModel.js" as Model

Rectangle {
  id: sheet
  property var controller
  readonly property var state: controller.state
  readonly property bool practising: sheet.state.required === true
  readonly property bool division: sheet.state.stage === "division"
  readonly property string stageName: division ? "Division" : "Multiplication"
  readonly property var stageResults: sheet.state.stage_results || ({})
  readonly property var bestTimes: sheet.state.best_times || ({})
  readonly property var currentBest: bestTimes[sheet.division ? "division" : "multiplication"] || null
  readonly property var passedStages: [stageResults.multiplication, stageResults.division].filter(function(result) { return result && result.passed })
  readonly property int roundNumber: Number(sheet.state.round || 1)
  readonly property int questionCount: Number(sheet.state.question_count || 50)
  readonly property int targetScore: Number(sheet.state.target || 40)
  readonly property int answeredCount: Number(sheet.state.answered || 0)
  readonly property int correctCount: Number(sheet.state.correct || 0)
  readonly property bool waiting: practising && answeredCount >= questionCount && !sheet.state.question
  readonly property bool guidedRetry: practising && !!sheet.state.question && sheet.state.question.stage === "retry"
  readonly property bool reviewing: practising && !!sheet.state.question && sheet.state.question.stage === "reveal"
  readonly property bool finished: !practising && (sheet.state.result === "complete" || sheet.state.result === "parent")
  readonly property bool compact: height < 850
  readonly property string family: Style.font.family
  color: Model.PALETTE.paper
  focus: true
  Keys.onEscapePressed: controller.handleEscape()

  function focusInput() {
    if (!visible) return
    if (controller.parentOpen) password.forceActiveFocus()
    // Finishing the questions must not focus the early-exit action: an
    // incidental Space would otherwise open Parent and pause the timer.
    else if (sheet.waiting) sheet.forceActiveFocus()
    else if (sheet.reviewing || !sheet.practising) mainAction.forceActiveFocus()
    else if (practising) answerField.forceActiveFocus()
  }
  onReviewingChanged: Qt.callLater(focusInput)
  onGuidedRetryChanged: Qt.callLater(focusInput)
  onWaitingChanged: Qt.callLater(focusInput)
  onDivisionChanged: Qt.callLater(function() { practiceScroll.contentY = 0; sheet.focusInput() })
  onPractisingChanged: Qt.callLater(function() { practiceScroll.contentY = 0; sheet.focusInput() })
  onVisibleChanged: if (visible) Qt.callLater(focusInput)
  Component.onCompleted: Qt.callLater(focusInput)
  Connections {
    target: sheet.controller
    function onParentOpenChanged() { password.text = ""; Qt.callLater(sheet.focusInput) }
    function onAnswerChanged() { Qt.callLater(sheet.focusInput) }
    function onBusyChanged() { if (!sheet.controller.busy) Qt.callLater(sheet.focusInput) }
  }

  component PracticeButton: Button {
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
    PracticeButton {
      id: parentButton
      text: controller.parentOpen ? "Back to practice" : practising ? "Esc · Parent" : "Close"
      enabled: !controller.parentBusy
      onClicked: controller.handleEscape()
    }
  }

  Flickable {
    id: practiceScroll
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
      objectName: "practiceHeading"
      width: parent.width
      text: practising ? "Stage " + (sheet.division ? "2" : "1") + " of 2 · " + sheet.stageName
        + (sheet.roundNumber > 1 ? " · Round " + sheet.roundNumber : " tables")
        : finished ? (sheet.state.result === "parent" ? "Session ended" : "Practice finished!") : "Multiplication, then division"
      textFormat: Text.PlainText
      color: Model.PALETTE.ink
      font { family: sheet.family; pixelSize: sheet.compact ? 30 : 40; bold: true }
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.WordWrap
    }
    StageResult {
      objectName: "multiplicationResult"
      visible: practising && sheet.division && result !== null
      result: sheet.stageResults.multiplication || null
      bestTime: sheet.bestTimes.multiplication || null
      compact: true
      family: sheet.family
      width: parent.width
    }
    Row {
      objectName: "stageResults"
      visible: finished && sheet.passedStages.length > 0
      width: parent.width
      spacing: 16
      Repeater {
        model: sheet.passedStages
        delegate: StageResult {
          required property var modelData
          objectName: "stageResult-" + modelData.stage
          result: modelData
          bestTime: sheet.bestTimes[modelData.stage] || null
          family: sheet.family
          width: (practiceColumn.width - 16 * (sheet.passedStages.length - 1)) / sheet.passedStages.length
        }
      }
    }
    Text {
      width: parent.width
      objectName: "roundScore"
      text: practising ? sheet.answeredCount + "/" + sheet.questionCount + " answered  ·  "
          + sheet.correctCount + " correct  ·  Goal: " + sheet.targetScore
        : finished ? (sheet.state.result === "parent" ? "The session was ended by a parent. Completed stage rewards are saved."
          : sheet.stageResults.division ? "Both stages passed. Well done!" : "Multiplication passed. Well done!")
        : "Tables 1–12 · Stage 1: 50 questions, 40 correct, up to 30 minutes\nStage 2: 25 questions in 15 minutes, 20 correct"
      color: Model.PALETTE.inkSoft
      font { family: sheet.family; pixelSize: 18 }
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.WordWrap
    }
    Row {
      objectName: "medalGoals"
      visible: !practising && !finished
      width: parent.width
      Repeater {
        model: ["gold", "silver", "bronze"]
        delegate: Column {
          required property string modelData
          required property int index
          width: practiceColumn.width / 3
          spacing: 4
          MedalBadge {
            objectName: "medalGoalBadge-" + parent.modelData
            anchors.horizontalCenter: parent.horizontalCenter
            width: 58; height: 62
            medal: parent.modelData
          }
          Text {
            objectName: "medalGoal-" + parent.modelData
            width: parent.width
            text: Model.medal(parent.modelData).name + " · " + parent.index + " wrong"
            color: Model.medal(parent.modelData).dark
            font { family: sheet.family; pixelSize: 17; bold: true }
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
          }
        }
      }
    }
    Row {
      objectName: "personalBests"
      visible: !practising && (!finished || sheet.passedStages.length === 0)
      width: parent.width
      spacing: 12
      Repeater {
        model: ["multiplication", "division"]
        delegate: Rectangle {
          id: personalBest
          required property string modelData
          readonly property var record: sheet.bestTimes[modelData] || null
          width: (practiceColumn.width - 12) / 2
          height: 76
          radius: 12
          color: "#fafbff"
          border.color: Model.PALETTE.rule
          Column {
            anchors { centerIn: parent }
            width: parent.width - 20
            spacing: 6
            Text {
              width: parent.width
              text: (personalBest.modelData === "division" ? "Division" : "Multiplication") + " · Best Time"
              color: Model.PALETTE.inkSoft
              font { family: sheet.family; pixelSize: 16 }
              horizontalAlignment: Text.AlignHCenter
              wrapMode: Text.WordWrap
            }
            Text {
              objectName: "bestTime-" + personalBest.modelData
              width: parent.width
              text: personalBest.record ? Model.clock(personalBest.record.seconds) : "No time yet"
              color: personalBest.record ? Model.PALETTE.mark : Model.PALETTE.inkSoft
              font { family: sheet.family; pixelSize: 22; bold: true }
              horizontalAlignment: Text.AlignHCenter
            }
          }
        }
      }
    }
    Rectangle {
      visible: practising
      width: parent.width
      height: 7
      radius: 4
      color: "#eef0f5"
      Rectangle {
        width: parent.width * Math.max(0, Math.min(1, sheet.answeredCount / sheet.questionCount))
        height: parent.height
        radius: parent.radius
        color: Model.PALETTE.mark
      }
    }
    Text {
      objectName: "practiceCountdown"
      visible: practising
      width: parent.width
      text: sheet.waiting ? (!sheet.division
          ? (sheet.correctCount >= sheet.targetScore ? "Starting Stage 2 · Division…" : "Starting another multiplication round…")
          : (sheet.correctCount >= sheet.targetScore ? "Practice finishes in " : "Next division round starts in ") + Model.clock(sheet.state.remaining))
        : Model.clock(sheet.state.remaining) + (sheet.division ? " left in this round" : " left to answer")
      color: sheet.waiting ? Model.PALETTE.ink : Model.PALETTE.inkSoft
      font { family: sheet.family; pixelSize: sheet.waiting ? 24 : 19; bold: sheet.waiting }
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.WordWrap
    }
    Text {
      objectName: "stageBestTime"
      visible: practising && sheet.currentBest !== null
      width: parent.width
      text: "Best Time · " + (sheet.currentBest ? Model.clock(sheet.currentBest.seconds) : "")
      color: Model.PALETTE.mark
      font { family: sheet.family; pixelSize: 16 }
      horizontalAlignment: Text.AlignHCenter
    }
    Text {
      objectName: "practiceQuestion"
      visible: practising
      width: parent.width
      text: sheet.waiting ? "All " + sheet.questionCount + " answered"
        : sheet.state.question ? sheet.state.question.a + (sheet.division ? " ÷ " : " × ") + sheet.state.question.b + " = "
            + (sheet.reviewing ? sheet.state.question.solution : "?") : "Getting your question…"
      color: Model.PALETTE.ink
      font { family: sheet.family; pixelSize: sheet.waiting ? 34 : sheet.compact ? 55 : 78; bold: true }
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.WordWrap
    }
    Text {
      objectName: "questionHelp"
      lineHeight: 1.25
      visible: sheet.guidedRetry || sheet.reviewing
      width: parent.width
      text: sheet.reviewing ? "Let's remember this fact. Choose Continue when you're ready."
        : sheet.state.question && sheet.state.question.hint
          ? sheet.state.question.hint
          : ""
      textFormat: Text.PlainText
      color: Model.PALETTE.inkSoft
      font { family: sheet.family; pixelSize: 18 }
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.WordWrap
    }
    TextField {
      id: answerField
      objectName: "answerField"
      visible: practising && !sheet.waiting && !sheet.reviewing
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
    PracticeButton {
      id: mainAction
      objectName: "practiceAction"
      anchors.horizontalCenter: parent.horizontalCenter
      visible: !sheet.waiting
      text: controller.busy ? "Checking…" : sheet.reviewing ? "Continue" : sheet.guidedRetry ? "Check retry"
        : practising ? "Check answer" : finished ? "Start another session" : "Start 50-question round"
      enabled: !controller.busy && controller.connected && sheet.state.active === true
        && sheet.state.locked === false && typeof sheet.state.school === "boolean"
        && (sheet.reviewing || !practising || controller.answer.length > 0)
      function activate() {
        if (!enabled) return
        if (sheet.reviewing) controller.acknowledge()
        else if (practising) controller.submit()
        else controller.start()
      }
      onClicked: activate()
      Keys.onReturnPressed: event => { if (!event.isAutoRepeat) activate() }
      Keys.onEnterPressed: event => { if (!event.isAutoRepeat) activate() }
    }
    Text {
      objectName: "roundGuidance"
      width: parent.width
      visible: practising && !sheet.guidedRetry && !sheet.reviewing && text.length > 0
      text: sheet.waiting ? (sheet.correctCount >= sheet.targetScore
          ? (sheet.division ? "You reached your goal! Practice finishes automatically when this timer ends."
            : "You reached your goal! Your multiplication answers are saved. Division starts automatically.")
          : (sheet.division ? "When this timer ends, try 25 more questions in 15 minutes. Aim for 20 correct."
            : "Try 25 more multiplication questions. Aim for 20 correct to reach division."))
        : sheet.state.last_round && !sheet.state.last_round.passed
          ? "Last round: " + sheet.state.last_round.correct + "/" + sheet.state.last_round.questions
            + ". Aim for 20/25 this round to " + (sheet.division ? "finish." : "reach division.")
        : sheet.state.migration_note || ""
      textFormat: Text.PlainText
      color: Model.PALETTE.inkSoft
      font { family: sheet.family; pixelSize: 17 }
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.WordWrap
    }
    Text {
      objectName: "practiceFeedback"
      visible: !controller.connected || (!sheet.guidedRetry && !sheet.reviewing)
      width: parent.width
      text: !controller.connected ? Model.errorText(controller.practiceService ? controller.practiceService.error : "service_unavailable")
        : (sheet.state.pause || controller.feedback || (sheet.waiting ? "Your answers are saved." : practising ? "Enter checks your answer. Take your time." : "Your progress is saved if you lock or restart."))
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
      objectName: "parentHelp"
      width: parent.width
      text: "Enter the parent password only to end this session early.\nThe timer is paused here. Choose Back to practice to continue."
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
    PracticeButton {
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
