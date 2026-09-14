"""Explicit local installation for Math Time's independent practice service."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tempfile

NAME = "peterholko-math-time"
VERSION = "1.3.0"
SOURCE = Path(__file__).resolve().parents[1]
PAYLOAD = Path("/usr/lib") / NAME
ETC = Path("/etc") / NAME
STATE = Path("/var/lib") / NAME
RECORD = STATE / "installation.json"
UNIT = NAME + ".service"
RUNTIME_FILES = ("core.py", "session.py", "auth.py", "runtime.py")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_target(path, owner=0):
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f"Refusing a symlink at {part}")
        if part.exists() and (part.stat().st_uid != owner or part.stat().st_mode & 0o022):
            raise ValueError(f"Expected an owner-controlled system path: {part}")


def payload(source):
    files = {}
    for name in RUNTIME_FILES:
        files[PAYLOAD / name] = ((source / "service" / name).read_bytes(), 0o644)
    files[PAYLOAD / "client.py"] = ((source / "client.py").read_bytes(), 0o644)
    files[Path("/etc/systemd/system") / UNIT] = ((source / "service" / UNIT).read_bytes(), 0o644)
    files[Path("/etc/pam.d") / NAME] = ((source / "service/pam.conf").read_bytes(), 0o644)
    files[Path("/usr/bin/omarchy-math-time-client")] = (
        b'#!/bin/bash\nexec /usr/bin/python3 -I /usr/lib/peterholko-math-time/client.py "$@"\n', 0o755)
    return files


def check_replacement(path, data, previous, upgrade):
    if path.exists() and digest(path.read_bytes()) != digest(data):
        if not upgrade or previous.get(str(path)) != digest(path.read_bytes()):
            raise ValueError(f"Refusing to replace an untracked or locally modified file: {path}")


def atomic_file(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    fd, name = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def read(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def configure(config, username):
    result = json.loads(json.dumps(config))
    users = result.setdefault("users", {})
    users.setdefault(username, {})
    # This release makes the app manual for every enrollment, including
    # accounts previously configured for daily or unlock-triggered practice.
    for options in users.values():
        options["trigger"] = "manual"
    result["version"] = 2
    return result


def install(args):
    account = pwd.getpwnam(args.user)
    if account.pw_uid == 0:
        raise ValueError("Enroll the child's account, not root.")
    for directory in (ETC, STATE, PAYLOAD):
        safe_target(directory)
    for directory in (ETC, STATE):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
    for path in (RECORD, ETC / "config.json"):
        safe_target(path)
    record = read(RECORD, {})
    files = payload(SOURCE)
    tracked = record.get("files", {})
    if record and record.get("version") != VERSION and not args.upgrade:
        raise ValueError("Rerun with --upgrade to update the installed service; progress will be retained.")
    if PAYLOAD.exists():
        for path in PAYLOAD.iterdir():
            if str(path) not in tracked or not path.is_file():
                raise ValueError(f"Unexpected installed payload at {path}")
    for path, (data, _mode) in files.items():
        safe_target(path)
        check_replacement(path, data, tracked, args.upgrade)
    config = configure(read(ETC / "config.json", {"version": 2, "users": {}}), args.user)
    for path, (data, mode) in files.items():
        atomic_file(path, data, mode)
    atomic_file(ETC / "config.json", (json.dumps(config, indent=2) + "\n").encode(), 0o600)
    record = {"version": VERSION, "files": {str(path): digest(data) for path, (data, _) in files.items()}}
    atomic_file(RECORD, (json.dumps(record, indent=2) + "\n").encode(), 0o600)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "--now", UNIT], check=True)
    subprocess.run(["systemctl", "restart", UNIT], check=True)
    print(f"Math Time installed for {args.user}: open the app and choose Start to begin 50 questions / 30 minutes.")
    print("Pass with 40/50; otherwise repeat 15-minute rounds with a 20/25 target.")
    print("A parent can end practice early using the parent/root password.")


def remove(args):
    for path in (ETC, STATE, PAYLOAD, RECORD, ETC / "config.json"):
        safe_target(path)
    record = read(RECORD, {})
    if not record:
        raise ValueError("No tracked Math Time service installation was found.")
    expected = payload(SOURCE)
    for name, checksum in record.get("files", {}).items():
        path = Path(name)
        if path not in expected:
            raise ValueError(f"Unexpected owned path: {path}")
        safe_target(path)
        if path.exists() and digest(path.read_bytes()) != checksum:
            raise ValueError(f"Preserve the locally modified file before removal: {path}")
    config = read(ETC / "config.json", {"version": 1, "users": {}})
    config["users"].pop(args.user, None)
    atomic_file(ETC / "config.json", (json.dumps(config, indent=2) + "\n").encode(), 0o600)
    if config["users"]:
        subprocess.run(["systemctl", "restart", UNIT], check=True)
    else:
        subprocess.run(["systemctl", "disable", "--now", UNIT], check=True)
        for name in record["files"]:
            Path(name).unlink(missing_ok=True)
        PAYLOAD.rmdir()
        RECORD.unlink()
        subprocess.run(["systemctl", "daemon-reload"], check=True)
    print(f"Removed Math Time enrollment for {args.user}. Saved practice history is retained.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", required=True)
    parser.add_argument("--trigger", choices=("manual",), help="Compatibility option; Math Time always starts manually.")
    parser.add_argument("--upgrade", action="store_true")
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args()
    if sys.platform != "linux" or os.geteuid() != 0:
        parser.error("Run with sudo on the Omarchy laptop.")
    try:
        (remove if args.remove else install)(args)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Math Time setup: {error}\n")


if __name__ == "__main__":
    main()
