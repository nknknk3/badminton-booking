"""Validate the actual Windows package and shut it down through its UI."""
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
env = os.environ.copy()
env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--remote-debugging-port=18770 --remote-debugging-address=127.0.0.1"
env["SMOKE_URL"] = "http://127.0.0.1:18768"
env["CDP_URL"] = "http://127.0.0.1:18770"
exe = Path(env.get("SMOKE_EXE", str(ROOT / "BadmintonBooking.exe")))
started = time.monotonic()
proc = subprocess.Popen([str(exe), "--port", "18768"], cwd=ROOT, env=env)
metrics = {}


def reachable(url):
    try:
        with urllib.request.urlopen(url, timeout=0.5) as response:
            return response.status == 200
    except Exception:
        return False


try:
    deadline = started + 90
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Package exited during startup: {proc.returncode}")
        if "backend_seconds" not in metrics and reachable(env["SMOKE_URL"] + "/api/system/health"):
            metrics["backend_seconds"] = round(time.monotonic() - started, 2)
        if reachable(env["CDP_URL"] + "/json/version"):
            metrics["native_engine_seconds"] = round(time.monotonic() - started, 2)
            break
        time.sleep(0.2)
    else:
        raise RuntimeError("Native engine startup timeout")
    subprocess.run(["node", str(ROOT / "tests" / "frontend_smoke.cjs")], env=env, cwd=ROOT, check=True, timeout=90)
    proc.wait(timeout=15)
    if reachable(env["SMOKE_URL"] + "/api/system/health"):
        raise RuntimeError("Backend survived application exit")
    metrics["exit_code"] = proc.returncode
    metrics["backend_stopped"] = True
    (ROOT / "runtime" / "packaged-result.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics), flush=True)
finally:
    if proc.poll() is None:
        try:
            req = urllib.request.Request(env["SMOKE_URL"] + "/api/system/shutdown", data=b"{}", headers={"X-Desktop-Action": "shutdown", "Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=3).close()
            proc.wait(timeout=12)
        except Exception:
            proc.terminate()
