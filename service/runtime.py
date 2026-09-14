"""Root-owned local practice service. JSON over a peer-authenticated Unix socket."""
import datetime
import json
import os
from pathlib import Path
import pwd
import signal
import socket
import socketserver
import struct
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auth import parent_password_ok
from core import Practice
from session import environment

NAME = "peterholko-math-time"
CONFIG = Path("/etc") / NAME / "config.json"
STATE = Path("/var/lib") / NAME / "practice.json"
SOCKET = Path("/run") / NAME / "sock"
MAX_MESSAGE = 8192


def atomic_json(path, value):
    fd, name = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


class Host:
    def __init__(self, config, saved, persist, verifier=parent_password_ok):
        self.lock = threading.RLock()
        self.config = config
        self.persist = persist
        self.verify = verifier
        self.models = {}
        self.users = {}
        self.auth_next = {}
        self.auth_busy = set()
        self.auth_failures = {}
        for username in config["users"]:
            uid = pwd.getpwnam(username).pw_uid
            self.users[uid] = username
            self.models[uid] = Practice(saved.get(username))

    def save(self):
        self.persist({self.users[uid]: model.data for uid, model in self.models.items()})

    def tick(self, now, day, environments):
        with self.lock:
            for uid, model in self.models.items():
                model.advance(now, day, environments.get(uid, {}))
            self.save()

    def dispatch(self, peer, message, now=None, day=None):
        now = time.monotonic() if now is None else now
        day = datetime.date.today().isoformat() if day is None else day
        if not isinstance(message, dict):
            return {"ok": False, "error": "invalid_request"}
        uid = peer
        if peer == 0 and isinstance(message.get("uid"), int):
            uid = message["uid"]
        if uid not in self.models:
            return {"ok": False, "error": "not_enrolled"}
        command = message.get("cmd")
        if command == "parent.end":
            password = message.get("password")
            with self.lock:
                if uid in self.auth_busy or now < self.auth_next.get(uid, 0):
                    return {"ok": False, "error": "try_later"}
                self.auth_busy.add(uid)
            try:
                valid = peer == 0 or (isinstance(password, str) and len(password) <= 1024
                                      and self.verify(password))
            except (OSError, ValueError):
                valid = False
            with self.lock:
                self.auth_busy.discard(uid)
                if not valid:
                    failures = min(6, self.auth_failures.get(uid, 0) + 1)
                    self.auth_failures[uid] = failures
                    self.auth_next[uid] = time.monotonic() + 2 ** failures
                    return {"ok": False, "error": "bad_password"}
                self.auth_failures[uid] = 0
                self.auth_next.pop(uid, None)
                self.models[uid].end_by_parent(day)
                self.save()
                return {"ok": True, "state": self.models[uid].snapshot(time.monotonic())}
        with self.lock:
            model = self.models[uid]
            previous = (model.data["round"], model.data["required"])
            # Judge deadlines before accepting an answer, even if the next
            # one-second daemon tick has not run yet.
            model.advance(now, day, model.environment)
            if previous != (model.data["round"], model.data["required"]):
                self.save()
            if command == "status":
                return model.snapshot(now)
            if command == "present":
                model.present(now, message.get("session"), message.get("question"),
                              message.get("visible") is True)
                return model.snapshot(now)
            if command == "start":
                result = model.start(day)
            elif command == "answer":
                result = model.answer(message.get("question"), message.get("answer", ""))
            elif command == "acknowledge":
                result = model.acknowledge(message.get("question"))
            else:
                return {"ok": False, "error": "unknown_command"}
            self.save()
            return {**result, "state": model.snapshot(now)}


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    slots = threading.BoundedSemaphore(16)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(3)
        try:
            _pid, uid, _gid = struct.unpack("3i", self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            raw = self.rfile.readline(MAX_MESSAGE + 1)
            if len(raw) > MAX_MESSAGE or not raw.endswith(b"\n"):
                return
            message = json.loads(raw)
            result = self.server.host.dispatch(uid, message)
            self.wfile.write((json.dumps(result) + "\n").encode())
        except (OSError, ValueError, TypeError):
            return


def main():
    if os.geteuid() != 0 or sys.platform != "linux":
        raise SystemExit("Run the installed service on the Omarchy laptop.")
    config = json.loads(CONFIG.read_text())
    saved = json.loads(STATE.read_text()) if STATE.exists() else {}
    host = Host(config, saved, lambda data: atomic_json(STATE, data))
    SOCKET.unlink(missing_ok=True)
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    with Server(str(SOCKET), Handler) as server:
        server.host = host
        # Access is checked using SO_PEERCRED, not supplementary groups, so
        # enrollment works immediately without a logout or a sudo exception.
        os.chmod(SOCKET, 0o666)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            while not stopping.is_set():
                environments = {uid: environment(uid, username) for uid, username in host.users.items()}
                host.tick(time.monotonic(), datetime.date.today().isoformat(), environments)
                stopping.wait(1)
        finally:
            server.shutdown()
            with host.lock:
                host.save()
            SOCKET.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
