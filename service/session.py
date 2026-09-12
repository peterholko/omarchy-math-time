"""Read logind and the optional standalone School Mode's public status."""
import json
from pathlib import Path
import subprocess


def properties(*args):
    result = subprocess.run(["loginctl", *args], text=True, capture_output=True, timeout=2)
    if result.returncode:
        return {}
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def school_status(username):
    path = Path("/var/lib/omarchy-kids-controls/status") / username / "school-mode/status.json"
    config_path = Path("/etc/omarchy-kids-controls/school-mode.json")
    # A missing optional plugin has no effect. A known enrollment with a
    # missing/invalid status defers Math Time rather than interrupting school.
    try:
        config = json.loads(config_path.read_text()) if config_path.exists() else {}
        enrolled = username in config.get("users", {})
        if not path.exists():
            return None if enrolled else False
        status = json.loads(path.read_text())
        if status.get("schemaVersion") != 1 or not isinstance(status.get("enabled"), bool):
            return None
        if not status["enabled"]:
            return False
        if status.get("mode") not in ("school", "free"):
            return None
        return status["mode"] == "school"
    except (OSError, ValueError, AttributeError):
        return None


def environment(uid, username):
    fallback = {"active": False, "locked": True, "school": school_status(username), "session": ""}
    try:
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        sessions = properties("show-user", str(uid), "-p", "Sessions").get("Sessions", "").split()
        for identifier in sessions:
            info = properties("show-session", identifier, "-p", "Type", "-p", "Class",
                              "-p", "Active", "-p", "LockedHint", "-p", "State")
            if info.get("Class") != "user" or info.get("Type") not in ("wayland", "x11"):
                continue
            if info.get("Active") != "yes" or info.get("State") not in ("active", "online"):
                continue
            return {**fallback, "active": True, "locked": info.get("LockedHint") != "no",
                    "session": boot + ":" + identifier}
    except (OSError, subprocess.TimeoutExpired):
        pass
    return fallback
