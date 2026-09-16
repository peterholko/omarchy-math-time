"""Render the real QML view in the portable Qt adapter; inspect the output PNGs."""
import argparse
from pathlib import Path
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from test_ui import APP, UiTest, Practice


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    test = UiTest("test_escape_requires_parent_and_pauses_presence")
    test.setUp()
    try:
        window = next(window for window in APP.allWindows() if isinstance(window, QQuickWindow))
        for width, height in ((1100, 780), (1280, 720), (800, 600)):
            window.resize(width, height)
            window.contentItem().setWidth(width)
            window.contentItem().setHeight(height)
            QTest.qWait(100)
            assert window.grabWindow().save(str(args.directory / f"practice-{width}x{height}.png"))
        test.step("escape")
        QTest.qWait(100)
        assert window.grabWindow().save(str(args.directory / "parent.png"))
        test.step("parent")
        QTest.qWait(100)
        assert window.grabWindow().save(str(args.directory / "checking.png"))
        test.step("bad-password")
        test.step("escape")
        for action in ("waiting", "waiting-fail", "retry", "guided", "reveal", "complete"):
            test.step(action)
            QTest.qWait(100)
            assert window.grabWindow().save(str(args.directory / f"{action}.png"))
        for action in ("idle", "parent-ok"):
            test.step(action)
            test.step("open")
            for width, height in ((1280, 720), (800, 600)):
                window.resize(width, height)
                window.contentItem().setWidth(width)
                window.contentItem().setHeight(height)
                QTest.qWait(100)
                assert window.grabWindow().save(str(args.directory / f"{action}-{width}x{height}.png"))
        model = Practice()
        model.advance(0, "2026-09-16", {"active": True, "locked": False, "school": True})
        test.apply_service_state(model.snapshot(0))
        test.step("open")
        assert test.view("practiceAction").property("enabled")
        QTest.qWait(100)
        assert window.grabWindow().save(str(args.directory / "school-manual-start.png"))
        assert test.activate_main_action()["request"] == {"cmd": "start"}
        assert model.start("2026-09-16")["ok"]
        test.apply_service_state(model.snapshot(0))
        assert test.step("inspect")["covering"]
        QTest.qWait(100)
        assert window.grabWindow().save(str(args.directory / "school-practice.png"))
    finally:
        test.doCleanups()


if __name__ == "__main__":
    main()
