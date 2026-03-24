from __future__ import annotations

import json
import os
import subprocess
import threading
from typing import Any, Dict

QUEUE_STATE_PATH = "/tmp/azurmix_queue_state.txt"
ENGINE_CONTAINER = os.getenv("AZURSMARTMIX_ENGINE_CONTAINER", "azursmartmix_engine")

_lock = threading.Lock()


def _empty_state() -> Dict[str, Any]:
    return {"now": None, "queue": [], "history": []}


def _normalize_state(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return _empty_state()

    now = data.get("now")
    queue = data.get("queue")
    history = data.get("history")

    if not isinstance(now, dict):
        now = None

    if not isinstance(queue, list):
        queue = []

    if not isinstance(history, list):
        history = []

    return {
        "now": now,
        "queue": queue,
        "history": history,
    }


def _read_local_state() -> Dict[str, Any]:
    if not os.path.exists(QUEUE_STATE_PATH):
        return _empty_state()

    try:
        with open(QUEUE_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _normalize_state(data)
    except Exception:
        return _empty_state()


def _read_engine_container_state() -> Dict[str, Any]:
    """
    Conservative fallback:
    read the queue state from the engine container, where the file is actually written.
    """
    try:
        proc = subprocess.run(
            [
                "docker",
                "exec",
                ENGINE_CONTAINER,
                "cat",
                QUEUE_STATE_PATH,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=3.0,
        )
    except Exception:
        return _empty_state()

    if proc.returncode != 0:
        return _empty_state()

    raw = (proc.stdout or "").strip()
    if not raw:
        return _empty_state()

    try:
        data = json.loads(raw)
    except Exception:
        return _empty_state()

    return _normalize_state(data)


def get_state() -> Dict[str, Any]:
    with _lock:
        local = _read_local_state()

        # Fast path: use local state if it already contains useful runtime data.
        if local.get("now") is not None or local.get("queue") or local.get("history"):
            return local

        # Fallback to the engine container because /tmp is container-local.
        remote = _read_engine_container_state()
        if remote.get("now") is not None or remote.get("queue") or remote.get("history"):
            return remote

        return local
