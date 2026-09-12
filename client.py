"""Unprivileged socket client and streaming bridge for the shell plugin."""
import argparse
import json
import os
import selectors
import socket
import sys
import time

SOCKET = "/run/peterholko-math-time/sock"
MAX_MESSAGE = 8192


def request(message):
    if not isinstance(message, dict):
        return {"ok": False, "error": "invalid_request"}
    data = (json.dumps(message) + "\n").encode()
    if len(data) > MAX_MESSAGE:
        return {"ok": False, "error": "invalid_request"}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
            stream.settimeout(25 if message.get("cmd") == "parent.end" else 3)
            stream.connect(SOCKET)
            stream.sendall(data)
            with stream.makefile("rb") as reply:
                raw = reply.readline(65537)
            if len(raw) > 65536:
                raise ValueError("reply too large")
            response = json.loads(raw)
            if not isinstance(response, dict):
                raise ValueError("invalid reply")
            return response
    except (OSError, ValueError):
        return {"ok": False, "error": "service_unavailable"}


def output(value):
    print(json.dumps(value), flush=True)


def watch():
    # One bridge watches policy and sends a short presence lease. If the
    # overlay or shell disappears, stdin closes and no more time is counted.
    selector = selectors.DefaultSelector()
    selector.register(sys.stdin.fileno(), selectors.EVENT_READ)
    presence = {"cmd": "present", "visible": False}
    pending = b""
    next_poll = 0.0
    while True:
        now = time.monotonic()
        if now >= next_poll:
            output(request(presence))
            next_poll = time.monotonic() + 1
        for key, _ in selector.select(max(0, next_poll - time.monotonic())):
            chunk = os.read(key.fd, 4096)
            if not chunk:
                return
            pending += chunk
            if len(pending) > MAX_MESSAGE:
                return
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                try:
                    value = json.loads(line)
                    presence = {"cmd": "present", "visible": value.get("visible") is True,
                                "session": str(value.get("session", "")),
                                "question": str(value.get("question", ""))}
                    next_poll = 0
                except (ValueError, AttributeError):
                    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("watch", "request", "status"))
    args = parser.parse_args()
    if args.action == "watch":
        watch()
    elif args.action == "status":
        output(request({"cmd": "status"}))
    else:
        raw = sys.stdin.buffer.readline(MAX_MESSAGE + 1)
        try:
            if len(raw) > MAX_MESSAGE:
                raise ValueError("request too large")
            output(request(json.loads(raw)))
        except ValueError:
            output({"ok": False, "error": "invalid_request"})


if __name__ == "__main__":
    try:
        main()
    except (BrokenPipeError, KeyboardInterrupt):
        pass
