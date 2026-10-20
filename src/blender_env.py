"""Locate the Blender executable and run scripts inside it (background mode).

Everything that needs bpy lives in Blender; the outer CLI only spawns it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 1) explicit override, 2) env var, 3) PATH, 4) known local installs
_CANDIDATES = [
    r"D:\software\blender\5.2.1\blender.exe",
    r"D:\software\blender\4.5\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
]


def find_blender(explicit: str | None = None) -> str:
    if explicit:
        p = Path(explicit)
        if p.exists():
            return str(p)
        raise FileNotFoundError(f"Blender not found: {explicit}")
    env = os.environ.get("BLENDER_EXE")
    if env and Path(env).exists():
        return env
    found = shutil.which("blender")
    if found:
        return found
    for c in _CANDIDATES:
        if Path(c).exists():
            return c
    raise FileNotFoundError(
        "Blender not found. Set BLENDER_EXE or pass --blender <path to blender.exe>")


def run_in_blender(script: str, args: list[str], timeout: int = 3600,
                   blender: str | None = None) -> dict:
    """Run `script` inside Blender, expecting it to write a JSON result file.

    Returns the parsed JSON dict (must contain an "ok" key).
    """
    exe = find_blender(blender)
    out_json = REPO_ROOT / "outputs" / "_last_result.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    if out_json.exists():
        out_json.unlink()

    cmd = [exe, "-b", "--factory-startup",
           "--python-exit-code", "1",
           "--python", str(REPO_ROOT / script), "--"] + list(args) + [
           "--result", str(out_json)]
    cmd = [str(c) for c in cmd if c is not None]
    print("[blender]", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)
    log = (proc.stdout or "") + (proc.stderr or "")
    if not out_json.exists():
        tail = "\n".join(log.splitlines()[-40:])
        raise RuntimeError(
            f"Blender run produced no result file (exit {proc.returncode}).\n{tail}")
    data = json.loads(out_json.read_text(encoding="utf-8"))
    data.setdefault("blender_log_tail", "\n".join(log.splitlines()[-60:]))
    return data


def print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))
