import QtQuick
import "MathModel.js" as Model

Rectangle {
  id: card
  property var result: null
  property var bestTime: null
  property bool compact: false
  property string family
  readonly property var award: result ? Model.medal(result.medal) : null
  readonly property string stageName: result && result.stage === "division" ? "Division" : "Multiplication"
  readonly property string score: result ? result.correct + "/" + result.questions + " correct · Round " + result.number : ""
  readonly property bool timed: result !== null && typeof result.completion_seconds === "number"
  readonly property string timeText: timed ? "Time · " + Model.clock(result.completion_seconds) : ""
  readonly property string bestText: bestTime ? (result && result.new_best ? "New Best Time · " : "Best Time · ") + Model.clock(bestTime.seconds) : ""
  color: "#fafbff"
  border.color: Model.PALETTE.rule
  radius: 12
  implicitHeight: compact ? Math.max(72, compactSummary.height + 24) : summary.height + 28

  Row {
    visible: card.compact
    anchors { verticalCenter: parent.verticalCenter; left: parent.left; right: parent.right; margins: 16 }
    spacing: 12
    MedalBadge {
      visible: card.award !== null
      width: 44; height: 47
      medal: card.result ? card.result.medal : ""
    }
    Column {
      id: compactSummary
      width: parent.width - (card.award ? 56 : 0)
      spacing: 4
      Text {
        objectName: card.objectName + "-summary"
        width: parent.width
        text: card.stageName + " passed" + (card.award ? " · " + card.award.name + " medal" : "")
        color: card.award ? card.award.dark : Model.PALETTE.good
        font { family: card.family; pixelSize: 17; bold: true }
        wrapMode: Text.WordWrap
      }
      Text {
        width: parent.width
        text: card.score + (card.timeText ? " · " + card.timeText : "")
        color: Model.PALETTE.inkSoft
        font { family: card.family; pixelSize: 15 }
        wrapMode: Text.WordWrap
      }
      Text {
        objectName: card.objectName + "-best"
        visible: text.length > 0
        width: parent.width
        text: card.bestText
        color: Model.PALETTE.mark
        font { family: card.family; pixelSize: 15; bold: true }
        wrapMode: Text.WordWrap
      }
    }
  }

  Column {
    id: summary
    visible: !card.compact
    anchors { top: parent.top; left: parent.left; right: parent.right; margins: 14 }
    spacing: 6
    Text {
      width: parent.width
      text: card.stageName
      color: Model.PALETTE.ink
      font { family: card.family; pixelSize: 20; bold: true }
      horizontalAlignment: Text.AlignHCenter
    }
    Item {
      width: parent.width; height: 128
      MedalBadge {
        anchors.centerIn: parent
        visible: card.award !== null
        width: 120; height: 128
        medal: card.result ? card.result.medal : ""
      }
      Text {
        anchors.centerIn: parent
        visible: card.award === null
        text: "✓"
        color: Model.PALETTE.good
        font { family: card.family; pixelSize: 64 }
      }
    }
    Text {
      objectName: card.objectName + "-medal"
      width: parent.width
      text: card.award ? card.award.name + " medal!" : "Passed!"
      color: card.award ? card.award.dark : Model.PALETTE.good
      font { family: card.family; pixelSize: 24; bold: true }
      horizontalAlignment: Text.AlignHCenter
    }
    Text {
      objectName: card.objectName + "-score"
      width: parent.width
      text: card.score
      color: Model.PALETTE.inkSoft
      font { family: card.family; pixelSize: 17 }
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.WordWrap
    }
    Text {
      objectName: card.objectName + "-wrong"
      width: parent.width
      text: card.result ? card.result.wrong + " wrong" : ""
      color: Model.PALETTE.inkSoft
      font { family: card.family; pixelSize: 17 }
      horizontalAlignment: Text.AlignHCenter
    }
    Text {
      objectName: card.objectName + "-time"
      visible: card.timed
      width: parent.width
      text: card.timeText
      color: Model.PALETTE.inkSoft
      font { family: card.family; pixelSize: 17 }
      horizontalAlignment: Text.AlignHCenter
    }
    Text {
      objectName: card.objectName + "-record"
      visible: text.length > 0
      width: parent.width
      text: card.bestText
      color: Model.PALETTE.mark
      font { family: card.family; pixelSize: 17; bold: true }
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.WordWrap
    }
  }
}
