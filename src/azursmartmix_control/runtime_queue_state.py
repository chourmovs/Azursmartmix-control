from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict

QUEUE_STATE_PATH = "/tmp/azurmix_queue_state.txt"

_lock = threading.Lock()


def get_state() -> Dict[str, Any]:
    with _lock:
        if not os.path.exists(QUEUE_STATE_PATH):
            return {"now": None, "queue": []}

        try:
            with open(QUEUE_STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"now": None, "queue": []}
            if "now" not in data:
                data["now"] = None
            if "queue" not in data or not isinstance(data["queue"], list):
                data["queue"] = []
            return data
        except Exception:
            return {"now": None, "queue": []}
