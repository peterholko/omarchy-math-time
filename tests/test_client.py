"""Real Unix socket/streaming bridge; peer identity is supplied by the fixture."""
import json
import os
from pathlib import Path
import pwd
import select
import socketserver
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "service"))
import client
from runtime import Host


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.socket = str(Path(self.temp.name) / "sock")
        self.uid = os.getuid()
        username = pwd.getpwuid(self.uid).pw_name
        self.host = Host({"users": {username: {"trigger": "manual"}}}, {}, lambda data: None)
        self.host.tick(0, "2026-09-12", {self.uid: {"active": True, "locked": False, "school": False, "session": "login"}})
        self.host.dispatch(self.uid, {"cmd": "start"}, now=0, day="2026-09-12")
        fixture = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                message = json.loads(self.rfile.readline())
                result = fixture.host.dispatch(fixture.uid, message)
                self.wfile.write((json.dumps(result) + "\n").encode())
        self.server = socketserver.UnixStreamServer(self.socket, Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.patch = patch("client.SOCKET", self.socket)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def test_status_and_answers_round_trip_through_socket(self):
        status = client.request({"cmd": "status"})
        self.assertTrue(status["required"])
        q = status["question"]
        result = client.request({"cmd": "answer", "question": q["id"], "answer": str(q["a"] * q["b"])})
        self.assertTrue(result["correct"])
        self.assertEqual(result["state"]["correct"], 1)
        self.assertTrue(result["state"]["required"])

    def test_invalid_input_and_unavailable_service_report_errors(self):
        self.assertEqual(client.request([])["error"], "invalid_request")
        self.assertEqual(client.request({"cmd": "parent.end", "password": "x" * 8192})["error"], "invalid_request")
        with patch("client.SOCKET", self.socket + "-missing"):
            self.assertEqual(client.request({"cmd": "status"})["error"], "service_unavailable")

    def test_guided_retry_reveal_and_acknowledgement_round_trip(self):
        status = client.request({"cmd": "status"})
        original = status["question"]
        first = client.request({"cmd": "answer", "question": original["id"], "answer": "999"})
        retry = first["state"]["question"]
        self.assertEqual(retry["stage"], "retry")
        self.assertNotIn("solution", retry)
        self.assertEqual(first["state"]["answered"], 1)
        second = client.request({"cmd": "answer", "question": retry["id"], "answer": "999"})
        reveal = second["state"]["question"]
        self.assertEqual(reveal["stage"], "reveal")
        self.assertEqual(reveal["solution"], original["a"] * original["b"])
        result = client.request({"cmd": "acknowledge", "question": reveal["id"]})
        self.assertTrue(result["acknowledged"])
        self.assertEqual(result["state"]["correct"], 0)
        self.assertEqual(result["state"]["answered"], 1)
        self.assertEqual(result["state"]["question"]["stage"], "first")

    def test_watch_streams_state_then_stops_on_shell_disconnect(self):
        program = "import sys; sys.path.insert(0, " + repr(str(ROOT)) + "); import client; client.SOCKET = " + repr(self.socket) + "; client.watch()"
        process = subprocess.Popen([sys.executable, "-I", "-c", program], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.assertTrue(select.select([process.stdout], [], [], 3)[0])
            status = json.loads(process.stdout.readline())
            process.stdin.write((json.dumps({"visible": True, "session": status["session"], "question": status["question"]["id"]}) + "\n").encode())
            process.stdin.flush()
            self.assertTrue(select.select([process.stdout], [], [], 3)[0])
            self.assertTrue(json.loads(process.stdout.readline())["show"])
            self.assertGreater(self.host.models[self.uid].present_until, 0)
            process.stdin.close()
            self.assertEqual(process.wait(timeout=3), 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
            process.stderr.close()
            if not process.stdin.closed:
                process.stdin.close()
