"""把任意 Playwright 导出的 session JSON 规整成本程序的格式。

    python tools/import_cookies.py 旧路径/venue_session.json

不带参数时读取程序目录下的 venue_session.json 并做一次自检。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENUE_HOST = "gyytygyy.xidian.edu.cn"
DEFAULT_OUT = PROJECT_ROOT / "venue_session.json"


def convert(src: Path) -> dict:
    payload = json.loads(src.read_text(encoding="utf-8-sig"))
    raw = payload.get("cookies") if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        raise ValueError("文件里没有 cookies 数组")
    cookies = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        domain = str(c.get("domain", "")) or VENUE_HOST
        cookies.append(
            {
                "name": c.get("name", ""),
                "value": c.get("value", ""),
                "domain": domain,
                "path": c.get("path", "/"),
                "httpOnly": bool(c.get("httpOnly", False)),
                "secure": bool(c.get("secure", False)),
            }
        )
    venue = [c for c in cookies if VENUE_HOST in c["domain"]]
    if not venue:
        raise ValueError(f"没有 {VENUE_HOST} 的 cookie")
    return {
        "final_url": payload.get("final_url", ""),
        "captured_at": payload.get("captured_at")
        or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cookies": cookies,
    }


def main() -> None:
    if len(sys.argv) > 1:
        src = Path(sys.argv[1])
    else:
        src = DEFAULT_OUT
    if not src.is_file():
        print(f"文件不存在: {src}")
        sys.exit(1)

    try:
        converted = convert(src)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"转换失败: {exc}")
        sys.exit(1)

    out = DEFAULT_OUT
    out.write_text(json.dumps(converted, indent=2, ensure_ascii=False), encoding="utf-8")
    venue_count = sum(1 for c in converted["cookies"] if VENUE_HOST in c["domain"])
    print(f"已写入 {out}（场馆 cookie {venue_count} 条）")


if __name__ == "__main__":
    main()
