"""Public automation API: submit(), run(), Job.poll(), Job.cancel().

Uses a separate Blender process; never clears the caller's open scene.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import time
import uuid
from datetime import datetime, timezone

VERSION = "0.9.0"
TERMINAL = {"COMPLETED", "REVIEW_REQUIRED", "FAILED", "CANCELLED", "TIMED_OUT"}


def write_json(path, data):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False),
                    encoding="utf-8")
    os.replace(temp, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _input_file(value, suffix):
    path = Path(value).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != suffix:
        raise ValueError(f"Expected an existing {suffix} file: {path}")
    return str(path)


def normalize_request(request):
    if not isinstance(request, dict):
        raise ValueError("Request must be a JSON object")
    allowed = {"action", "source", "target", "profile", "model", "motion",
               "output_root", "timeout", "render", "preset", "ground_motion", "cuff_physics"}
    unknown = set(request) - allowed
    if unknown:
        raise ValueError(f"Unknown request fields: {sorted(unknown)}")
    data = dict(request)
    action = data.get("action")
    if action not in {"inspect", "fit", "validate"}:
        raise ValueError("action must be inspect, fit or validate")
    fields = {"inspect": ("source", "target"), "fit": ("profile",),
              "validate": ("model",)}[action]
    for key in fields:
        if not data.get(key):
            raise ValueError(f"Missing field: {key}")
        data[key] = _input_file(data[key], ".json" if key == "profile" else ".pmx")
    if data.get("profile") and "profile" not in fields:
        data["profile"] = _input_file(data["profile"], ".json")
    if data.get("motion"):
        data["motion"] = _input_file(data["motion"], ".vmd")
    if not data.get("output_root"):
        raise ValueError("output_root is required")
    data["output_root"] = str(Path(data["output_root"]).expanduser().resolve())
    timeout = data.get("timeout", 1800)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 1 <= timeout <= 86400:
        raise ValueError("timeout must be 1..86400 seconds")
    data["timeout"] = timeout
    if "render" in data and not isinstance(data["render"], bool):
        raise ValueError("render must be a boolean")
    if 'ground_motion' in data and not isinstance(data['ground_motion'],bool):
        raise ValueError('ground_motion must be a boolean')
    if data.get('ground_motion') and (action!='fit' or not data.get('motion')):
        raise ValueError('ground_motion requires fit and a motion VMD')
    if 'cuff_physics' in data and not isinstance(data['cuff_physics'],bool):
        raise ValueError('cuff_physics must be boolean')
    if data.get('cuff_physics') and action!='fit':
        raise ValueError('cuff_physics requires fit')
    if data.get("preset", "conservative") not in {"conservative", "keqing_daniya"}:
        raise ValueError("Unknown preset")
    return data


class Job:
    def __init__(self, process, directory, log, timeout):
        self.process = process
        self.directory = Path(directory)
        self._log = log
        self.timeout = timeout
        self.started = time.monotonic()

    def _finish(self, state, message):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=10)
        result = {"schema_version": 1, "version": VERSION, "ok": False,
                  "accepted": False, "state": state,
                  "error": {"code": state, "message": message},
                  "job_dir": str(self.directory), "log": str(self.directory / "blender.log")}
        write_json(self.directory / "result.json", result)
        write_json(self.directory / "status.json", {"state": state, "stage": state.lower()})
        self._log.close()
        return result

    def poll(self):
        code = self.process.poll()
        if code is None:
            if time.monotonic() - self.started > self.timeout:
                return self._finish("TIMED_OUT", "Blender worker exceeded its time limit")
            try:
                status = read_json(self.directory / "status.json")
                if status.get("state") in TERMINAL:
                    return {"state": "RUNNING", "stage": "finalizing"}
                return status
            except (FileNotFoundError, json.JSONDecodeError):
                return {"state": "RUNNING", "stage": "starting"}
        result_file = self.directory / "result.json"
        if not result_file.exists():
            return self._finish("FAILED", f"Blender exited with code {code} without a result; see blender.log")
        result = read_json(result_file)
        self._log.close()
        if code != 0 and result.get("ok"):
            return self._finish("FAILED", f"Worker reported success but exited with code {code}")
        return result

    def cancel(self):
        if self.process.poll() is not None:
            return self.poll()
        return self._finish("CANCELLED", "Cancelled by caller")


def submit(request, blender):
    data = normalize_request(request)
    exe = Path(blender).resolve()
    if not exe.is_file():
        raise ValueError(f"Blender executable not found: {exe}")
    job_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:10]
    directory = Path(data["output_root"]) / job_id
    directory.mkdir(parents=True, exist_ok=False)
    data.update(job_dir=str(directory), schema_version=1, version=VERSION)
    write_json(directory / "request.json", data)
    write_json(directory / "status.json", {"state": "RUNNING", "stage": "starting"})
    log = (directory / "blender.log").open("wb")
    command = [str(exe), "-b", "--factory-startup", "--python-exit-code", "1",
               "--python", str(Path(__file__).with_name("worker.py")), "--",
               "--request", str(directory / "request.json")]
    try:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as exc:
        log.close()
        write_json(directory / "result.json", {"state": "FAILED", "ok": False,
                   "accepted": False, "error": {"code": "LAUNCH_FAILED", "message": str(exc)}})
        raise
    return Job(process, directory, log, data["timeout"])


def run(request, blender):
    job = submit(request, blender)
    try:
        while True:
            result = job.poll()
            if result.get("state") in TERMINAL:
                return result
            time.sleep(0.2)
    except BaseException:
        if job.process.poll() is None:
            job.cancel()
        raise
