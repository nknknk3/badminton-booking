"""Native integration probe; no upstream login or booking requests."""
import faulthandler
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
trace = (ROOT / "runtime" / "native-trace.log").open("w", encoding="utf-8")
faulthandler.enable(trace)
faulthandler.dump_traceback_later(25, repeat=True, file=trace)

import webview

original_start = webview.start
started = time.monotonic()


def probe_start(watch_shutdown, **kwargs):
    def probe():
        window = webview.windows[0]
        if not window.events.loaded.wait(30):
            raise RuntimeError("Native UI did not load")
        result = {"loaded_seconds": round(time.monotonic() - started, 2),
                  "title": window.evaluate_js("document.title"),
                  "text": window.evaluate_js("document.body.innerText")[:1500]}
        (ROOT / "runtime" / "native-result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        # destroy follows the same window closed event as clicking its close button.
        window.destroy()
    return original_start(probe, **kwargs)


webview.start = probe_start
import run
sys.argv = ["run.py", "--port", "18766"]
run.main()
faulthandler.cancel_dump_traceback_later()
