from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import docker
from docker.errors import DockerException, NotFound


@dataclass(frozen=True)
class ContainerInfo:
    name: str
    id: str
    image: str
    status: str
    created_at: Optional[str]
    health: Optional[str]
    started_at: Optional[str]


class DockerClient:
    """Read-only Docker wrapper for control-plane introspection.

    v1 helpers:
    - container status summary (age/uptime)
    - parse engine logs to extract *human titles* from 'preprocess:' lines
      and compute "upcoming" after the current track (Icecast title).
    """

    _RE_PREPROCESS = re.compile(r"\bpreprocess:\s*(?P<rest>.+?)\s*$", re.IGNORECASE)
    _RE_LEADING_IDX = re.compile(r"^\s*\d+\s*[\.\)]\s*")  # "1. " or "1) "
    _RE_SAFE_ARROW = re.compile(r"\s*->\s*safe_[0-9a-f]{8,}\.wav\b", re.IGNORECASE)
    _RE_PAREN_TRAIL = re.compile(r"\s*\(.*\)\s*$")
    _RE_EXT = re.compile(r"\.(mp3|wav|flac|ogg|m4a|aac)\s*$", re.IGNORECASE)

    def __init__(self) -> None:
        self.client = docker.from_env()

    def ping(self) -> bool:
        try:
            self.client.ping()
            return True
        except DockerException:
            return False

    def get_container_info(self, name: str) -> Optional[ContainerInfo]:
        try:
            c = self.client.containers.get(name)
        except NotFound:
            return None
        except DockerException:
            return None

        attrs = getattr(c, "attrs", {}) or {}
        state = (attrs.get("State") or {})
        health = None
        if isinstance(state.get("Health"), dict):
            health = state["Health"].get("Status")

        created = attrs.get("Created")
        started = state.get("StartedAt")
        image = ""
        try:
            image = (attrs.get("Config") or {}).get("Image") or ""
        except Exception:
            image = ""

        return ContainerInfo(
            name=name,
            id=c.id[:12],
            image=image,
            status=getattr(c, "status", "unknown"),
            created_at=created,
            health=health,
            started_at=started,
        )

    def tail_logs(self, name: str, tail: int = 300) -> str:
        """Return last N lines of container logs (best-effort)."""
        try:
            c = self.client.containers.get(name)
            raw: bytes = c.logs(tail=tail, timestamps=True)  # type: ignore[assignment]
            return raw.decode("utf-8", errors="replace")
        except NotFound:
            return f"[control] container not found: {name}\n"
        except DockerException as e:
            return f"[control] docker error: {e}\n"
        except Exception as e:
            return f"[control] unexpected error: {e}\n"

    def runtime_summary(self, engine_name: str, sched_name: str) -> Dict[str, Any]:
        now = dt.datetime.now(dt.timezone.utc)
        return {
            "now_utc": now.isoformat(),
            "docker_ping": self.ping(),
            "engine": self._container_info_dict(engine_name, now),
            "scheduler": self._container_info_dict(sched_name, now),
        }

    def _container_info_dict(self, name: str, now: dt.datetime) -> Dict[str, Any]:
        info = self.get_container_info(name)
        if not info:
            return {"name": name, "present": False}

        created_dt = self._parse_docker_ts(info.created_at)
        started_dt = self._parse_docker_ts(info.started_at)

        age_s = int((now - created_dt).total_seconds()) if created_dt else None
        uptime_s = int((now - started_dt).total_seconds()) if started_dt else None

        return {
            "present": True,
            "name": info.name,
            "id": info.id,
            "image": info.image,
            "status": info.status,
            "health": info.health,
            "created_at": info.created_at,
            "started_at": info.started_at,
            "age_s": age_s,
            "uptime_s": uptime_s,
        }

    @staticmethod
    def _parse_docker_ts(ts: Optional[str]) -> Optional[dt.datetime]:
        if not ts:
            return None
        try:
            if ts.endswith("Z"):
                ts = ts[:-1] + "+00:00"
            if "." in ts:
                head, tail = ts.split(".", 1)
                frac = re.findall(r"^\d+", tail)
                if frac:
                    frac_digits = frac[0][:6].ljust(6, "0")
                    rest = tail[len(frac[0]) :]
                    ts = f"{head}.{frac_digits}{rest}"
            return dt.datetime.fromisoformat(ts)
        except Exception:
            return None

    @staticmethod
    def _dedupe_keep_order(items: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for x in items:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    def _clean_preprocess_title(self, rest: str) -> Optional[str]:
        """Convert 'preprocess:' payload into a clean 'Artist - Title' string.

        Input examples:
          "1. Daddy Freddy & Tenor Fly - Go Freddy Go.mp3 -> safe_xxx.wav (silence=... LUFS ...)"
          "derrick_howard_-_behold_i_live_[1973].mp3 -> safe_....wav (...)"

        Output:
          "Daddy Freddy & Tenor Fly - Go Freddy Go"
          "derrick howard - behold i live [1973]" (underscores -> spaces)
        """
        s = (rest or "").strip()
        if not s:
            return None

        # Remove leading index "1. "
        s = self._RE_LEADING_IDX.sub("", s).strip()

        # If it contains "-> safe_xxx.wav", keep only left side
        if "->" in s:
            left = s.split("->", 1)[0].strip()
            s = left

        # Remove trailing parenthetical leftovers (just in case)
        s = self._RE_PAREN_TRAIL.sub("", s).strip()

        # Keep basename if it's a path
        s = os.path.basename(s)

        # Remove extension
        s = self._RE_EXT.sub("", s).strip()

        # Normalize underscores to spaces
        s = s.replace("_-_", " - ")
        s = s.replace("_", " ")
        s = re.sub(r"\s+", " ", s).strip()

        # If still empty, drop
        return s or None

    def extract_preprocess_titles(self, engine_container: str, tail: int = 2500) -> Dict[str, Any]:
        """Extract cleaned titles from engine logs 'preprocess:' lines."""
        txt = self.tail_logs(engine_container, tail=tail)
        if not txt or txt.startswith("[control]"):
            return {
                "ok": False,
                "source": "engine_logs",
                "engine_container": engine_container,
                "error": txt.strip() if txt else "empty logs",
                "titles": [],
            }

        titles: List[str] = []
        for line in txt.splitlines():
            m = self._RE_PREPROCESS.search(line)
            if not m:
                continue
            rest = (m.group("rest") or "").strip()
            t = self._clean_preprocess_title(rest)
            if t:
                titles.append(t)

        return {
            "ok": True,
            "source": "engine_logs",
            "engine_container": engine_container,
            "titles": titles,
            "count": len(titles),
        }

    def compute_upcoming_from_preprocess(
        self,
        engine_container: str,
        current_title: Optional[str],
        n: int = 10,
        tail: int = 2500,
    ) -> Dict[str, Any]:
        """Compute upcoming titles from preprocess logs after current_title.

        - Find LAST occurrence of current_title in the cleaned preprocess sequence
        - Return the next unique titles (keep order) limited to n
        - If not found: fallback to last chunk as "best effort"
        """
        data = self.extract_preprocess_titles(engine_container, tail=tail)
        if not data.get("ok"):
            return {"ok": False, "error": data.get("error"), "upcoming": [], "source": "engine_logs"}

        titles = data.get("titles") or []
        titles = [t for t in titles if isinstance(t, str) and t.strip()]
        if not titles:
            return {"ok": False, "error": "no preprocess titles found", "upcoming": [], "source": "engine_logs"}

        cur = (current_title or "").strip()
        start_idx = None

        if cur:
            for i in range(len(titles) - 1, -1, -1):
                if titles[i].strip() == cur:
                    start_idx = i + 1
                    break

        if start_idx is None:
            chunk = titles[-(n * 4) :]
            chunk = self._dedupe_keep_order(chunk)
            return {
                "ok": True,
                "source": "engine_logs_fallback_tail",
                "current_title_found": False,
                "current_title": current_title,
                "upcoming": chunk[:n],
            }

        chunk2 = titles[start_idx:]
        chunk2 = self._dedupe_keep_order(chunk2)
        return {
            "ok": True,
            "source": "engine_logs_after_current",
            "current_title_found": True,
            "current_title": current_title,
            "upcoming": chunk2[:n],
        }
