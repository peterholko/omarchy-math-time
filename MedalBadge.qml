import QtQuick
import QtQuick.Shapes
import "MathModel.js" as Model

// Vector artwork scales cleanly on laptop and external displays. The text
// beside it identifies the award without relying on color or emoji fonts.
Item {
  id: badge
  property string medal: "gold"
  readonly property var colors: Model.medal(medal) || Model.MEDALS.gold
  implicitWidth: 160
  implicitHeight: 170

  Item {
    width: 160
    height: 170
    anchors.centerIn: parent
    scale: Math.min(badge.width / width, badge.height / height)

    Shape {
      anchors.fill: parent
      ShapePath {
        strokeWidth: 0
        strokeColor: "transparent"
        fillColor: badge.colors.ribbon
        PathSvg { path: "M 45 86 L 79 101 L 60 165 L 43 146 L 20 149 Z" }
      }
      ShapePath {
        strokeWidth: 0
        strokeColor: "transparent"
        fillColor: Qt.lighter(badge.colors.ribbon, 1.13)
        PathSvg { path: "M 81 101 L 115 86 L 140 149 L 117 146 L 100 165 Z" }
      }
    }
    Rectangle {
      x: 22; y: 8; width: 116; height: 116; radius: 58
      color: badge.colors.dark
      Rectangle {
        anchors.fill: parent; anchors.margins: 3
        radius: width / 2
        gradient: Gradient {
          GradientStop { position: 0; color: badge.colors.light }
          GradientStop { position: 1; color: badge.colors.fill }
        }
      }
      Rectangle {
        anchors.fill: parent; anchors.margins: 12
        radius: width / 2
        color: "transparent"
        border.color: badge.colors.dark
        border.width: 1.5
      }
    }
    Shape {
      anchors.fill: parent
      ShapePath {
        strokeColor: badge.colors.dark
        strokeWidth: 2
        fillColor: "#fffdf5"
        joinStyle: ShapePath.RoundJoin
        PathSvg { path: "M 80 35 L 90 55 L 113 58 L 96 74 L 100 97 L 80 86 L 60 97 L 64 74 L 47 58 L 70 55 Z" }
      }
    }
    Rectangle { x: 7; y: 34; width: 7; height: 7; radius: 2; rotation: 45; color: badge.colors.fill }
    Rectangle { x: 144; y: 17; width: 10; height: 10; radius: 2; rotation: 45; color: badge.colors.fill }
    Rectangle { x: 147; y: 104; width: 5; height: 5; radius: 2.5; color: badge.colors.ribbon }
  }
}
