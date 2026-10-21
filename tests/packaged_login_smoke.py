"""Exercise one-click login in the exe without entering any credentials."""
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:18771"


def request(path, method="GET", headers=None):
    req = urllib.request.Request(BASE + path, method=method, headers=headers or {},
                                 data=b"{}" if method == "POST" else None)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


def debug_open(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2) as response:
            return any(page.get("type") == "page" for page in json.load(response))
    except Exception:
        return False


proc = subprocess.Popen([str(ROOT / "BadmintonBooking.exe"), "--headless", "--port", "18771"], cwd=ROOT)
try:
    for _ in range(60):
        try:
            request("/api/system/health")
            break
        except Exception:
            time.sleep(0.5)
    else:
        raise RuntimeError("Backend not ready")
    auth = request("/api/auth/status")
    log = ROOT / "logs" / "app.log"
    offset = len(log.read_text(encoding="utf-8"))
    initial = request("/api/auth/browser-login", "POST")
    if initial["state"] not in {"starting", "waiting"}:
        raise RuntimeError(initial["message"])
    deadline = time.monotonic() + 25
    poll_seconds = []
    while time.monotonic() < deadline:
        time.sleep(2)
        polled = time.monotonic()
        status = request("/api/auth/browser-login")
        poll_seconds.append(time.monotonic() - polled)
        if status["state"] not in {"starting", "waiting"}:
            raise RuntimeError(status["message"])
    matches = re.findall(r"CDP 端口 (\d+)", log.read_text(encoding="utf-8")[offset:])
    port = int(matches[-1])
    if not debug_open(port):
        raise RuntimeError("Login window not reachable after 25 seconds")
    cancelled = request("/api/auth/browser-login", "DELETE")
    for _ in range(10):
        if not debug_open(port):
            break
        time.sleep(0.5)
    else:
        raise RuntimeError("Cancelled browser still running")
    assert cancelled["state"] == "cancelled"
    result = {"version": request("/api/system/health")["version"],
              "recovered_session_valid": auth["logged_in"],
              "login_waiting_after_25s": True,
              "login_browser_connected": True,
              "cancel_closed_browser": True,
              "max_status_request_seconds": round(max(poll_seconds), 3)}
    (ROOT / "runtime" / "packaged-login-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result), flush=True)
finally:
    try:
        request("/api/auth/browser-login", "DELETE")
        request("/api/system/shutdown", "POST", {"X-Desktop-Action": "shutdown"})
        proc.wait(timeout=15)
    except Exception:
        proc.terminate()
