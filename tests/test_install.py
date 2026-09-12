"""Exercise file installation/upgrades/removal in a temporary system tree."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import pwd
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "service"))
import install


class InstallTest(unittest.TestCase):
    def test_install_upgrade_and_remove_preserve_progress_and_other_services(self):
        with tempfile.TemporaryDirectory() as temporary, contextlib.ExitStack() as stack:
            base = Path(temporary)
            files = {base / path.relative_to("/"): contents for path, contents in install.payload(ROOT).items()}
            payload = base / "usr/lib/peterholko-math-time"
            etc = base / "etc/peterholko-math-time"
            state = base / "var/lib/peterholko-math-time"
            record = state / "installation.json"
            stack.enter_context(patch.multiple(install, PAYLOAD=payload, ETC=etc, STATE=state, RECORD=record))
            stack.enter_context(patch("install.payload", return_value=files))
            # The test account owns this private tree; real setup requires root.
            stack.enter_context(patch("install.safe_target", side_effect=lambda path: self.assertTrue(path.is_relative_to(base))))
            commands = stack.enter_context(patch("install.subprocess.run"))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            username = pwd.getpwuid(os.getuid()).pw_name
            account = argparse.Namespace(pw_uid=1000)
            stack.enter_context(patch("install.pwd.getpwnam", return_value=account))
            args = argparse.Namespace(user=username, trigger="unlock", upgrade=False)
            other = base / "usr/lib/peterholko-screen-time/untouched"
            other.parent.mkdir(parents=True)
            other.write_text("other service")
            install.install(args)
            self.assertTrue(record.exists())
            self.assertEqual((etc / "config.json").stat().st_mode & 0o777, 0o600)
            progress = state / "practice.json"
            progress.write_text('{"saved-progress": 900}')
            runtime = payload / "runtime.py"
            original, mode = files[runtime]
            files[runtime] = (original + b"\n# upgrade fixture\n", mode)
            args.upgrade = True
            args.trigger = None
            install.install(args)
            self.assertEqual(progress.read_text(), '{"saved-progress": 900}')
            self.assertEqual(json.loads((etc / "config.json").read_text())["users"][username]["trigger"], "unlock")
            self.assertIn(b"upgrade fixture", runtime.read_bytes())
            install.remove(args)
            self.assertFalse(payload.exists())
            self.assertFalse(record.exists())
            self.assertTrue(progress.exists())
            self.assertEqual(other.read_text(), "other service")
            for call in commands.call_args_list:
                self.assertEqual(call.args[0][0], "systemctl")
                self.assertNotIn("screen-time", " ".join(call.args[0]))

    def test_installer_rejects_symlinks_in_system_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "owned"
            target.write_text("content")
            link = Path(temporary) / "link"
            link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlink"):
                install.safe_target(link)
