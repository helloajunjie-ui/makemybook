"""
build_exe.py — 一键打包脚本
=============================
流程：
  1. npm run build（构建前端 dist）
  2. PyInstaller --onefile（打包后端为单 EXE）

用法：
  python build_exe.py

输出：
  dist/DreamEngine.exe
"""

import subprocess
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")


def step(msg: str):
    print(f"\n{'='*60}")
    print(f"  >>> {msg}")
    print(f"{'='*60}")


def run(cmd: list[str], cwd: str):
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [FAIL] return code: {result.returncode}")
        print(result.stderr)
        sys.exit(1)
    if result.stdout:
        print(result.stdout.strip())


def main():
    # ── Step 1: 构建前端 ──
    step("[1/2] 构建前端静态文件 (npm run build)")
    run("npm run build", FRONTEND_DIR)

    frontend_dist = os.path.join(FRONTEND_DIR, "dist")
    if not os.path.isdir(frontend_dist):
        print("  [FAIL] 前端构建产物不存在: frontend/dist")
        sys.exit(1)
    print(f"  [OK] 前端构建完成: {frontend_dist}")

    # ── Step 2: PyInstaller 打包 ──
    step("[2/2] PyInstaller 打包为单 EXE")
    os.makedirs(DIST_DIR, exist_ok=True)

    pyinstaller_args = [
        "pyinstaller",
        "--onefile",
        "--name", "DreamEngine",
        "--distpath", DIST_DIR,
        "--add-data", f"{frontend_dist};frontend/dist",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "aiosqlite",
        "--hidden-import", "numpy",
        "--hidden-import", "tiktoken_ext.openai_public",
        "--hidden-import", "tiktoken_ext",
        os.path.join(BACKEND_DIR, "run.py"),
    ]

    run(" ".join(pyinstaller_args), PROJECT_ROOT)

    exe_path = os.path.join(DIST_DIR, "DreamEngine.exe")
    if os.path.isfile(exe_path):
        print(f"\n  ✅ 打包成功: {exe_path}")
        print(f"     文件大小: {os.path.getsize(exe_path) / 1024 / 1024:.1f} MB")
    else:
        print(f"\n  [FAIL] 未找到输出文件: {exe_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
