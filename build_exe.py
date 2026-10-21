"""打包为快速启动的桌面 exe + _internal 依赖目录。

    python build_exe.py

产物：BadmintonBooking.exe + _internal/
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def ensure_frontend() -> None:
    print("[1/3] 构建前端…")
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        sys.exit("找不到 npm，请先安装 Node.js 并执行 cd frontend && npm install")
    subprocess.run([npm, "run", "build"], cwd=ROOT / "frontend", check=True)


def build() -> None:
    try:
        import PyInstaller.__main__  # noqa: F401
    except ImportError:
        sys.exit("缺少 PyInstaller：pip install pyinstaller")

    print("[2/3] PyInstaller 打包…")
    args = [
        str(ROOT / "run.py"),
        "--name",
        "BadmintonBooking",
        "--onedir",
        "--noconsole",
        "--noconfirm",
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD),
        "--specpath",
        str(BUILD),
        "--add-data",
        f"{ROOT / 'frontend' / 'dist'}{os.pathsep}frontend/dist",
        "--collect-all",
        "webview",
        "--collect-all",
        "clr_loader",
        "--hidden-import",
        "webview.platforms.edgechromium",
        "--hidden-import",
        "clr",
        "--hidden-import",
        "websockets",
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.loops.asyncio",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.http.h11_impl",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        "--hidden-import",
        "uvicorn.lifespan.on",
        "--hidden-import",
        "uvicorn.lifespan.off",
        "--collect-submodules",
        "apscheduler",
        "--collect-submodules",
        "aiosqlite",
        "--collect-submodules",
        "pyngrok",
        "--collect-submodules",
        "anyio",
    ]
    icon = ROOT / "assets" / "app.ico"
    if icon.is_file():
        args += ["--icon", str(icon)]
    import PyInstaller.__main__ as pyi

    pyi.run(args)


def cleanup() -> None:
    print("[3/3] 整理产物…")
    release = DIST / "BadmintonBooking"
    exe = release / "BadmintonBooking.exe"
    if not exe.is_file():
        return
    final = ROOT / "BadmintonBooking.exe"
    backup = ROOT / "BadmintonBooking.previous.exe"
    if final.exists() and not backup.exists():
        shutil.copy2(final, backup)
    shutil.copytree(release / "_internal", ROOT / "_internal", dirs_exist_ok=True)
    shutil.copy2(exe, final)
    shutil.copy2(ROOT / "README.md", release / "README.md")
    shutil.copy2(ROOT / "config.example.json", release / "config.example.json")
    print(f"\n✅ 打包完成: {final}")
    print(f"   体积: {final.stat().st_size / 1024 / 1024:.1f} MB")
    print("   双击即可运行；_internal/ 必须与 exe 一起保留。")


if __name__ == "__main__":
    ensure_frontend()
    build()
    cleanup()
