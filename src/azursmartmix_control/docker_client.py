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


@dataclass(frozen=True)
class NextEntry:
    ts_raw: str
    ts: Optional[dt.datetime]
    title_raw: str
    title_norm: str
    playlist: str


class DockerClient:
    """Read-only Docker wrapper for control-plane introspection.

    Key features:
    - Tail logs from engine/scheduler containers.
    - Parse scheduler logs for NEXT entries (title + playlist).
    - Infer 'Now Playing playlist' by matching Icecast title against scheduler NEXT title.
    - Provide engine STREAM_START hint to display 'next' without UI lag.
    """

    # --- engine preprocess lines (kept for backward compat / debug) ---
    _RE_PREPROCESS = re.compile(r"\bpreprocess:\s*(?P<rest>.+?)\s*$", re.IGNORECASE)
    _RE_LEADING_IDX = re.compile(r"^\s*\d+\s*[\.\)]\s*")  # "1. " or "1) "
    _RE_PAREN_TRAIL = re.compile(r"\s*\(.*\)\s*$")
    _RE_EXT = re.compile(r"\.(mp3|wav|flac|ogg|m4a|aac)\s*$", re.IGNORECASE)

    # --- docker timestamps prefix (when docker logs called with timestamps=True) ---
    # Example:
    # 2026-02-20T12:12:58.106123456Z 2026-02-20 12:12:58,106 INFO ...
    _RE_DOCKER_TS_PREFIX = re.compile(r"^\s*\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+")

    # --- scheduler NEXT parsing (robust, with optional docker timestamp prefix) ---
    # Example:
    # 2026-02-20 12:12:58,106 INFO azurmixd.scheduler - NEXT | title="vanzo_-_me_and_you" | playlist="Promotion" | ...
    _RE_SCHED_NEXT = re.compile(
        r"""(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\s+.*?\bazurmixd\.scheduler\b.*?\bNEXT\s*\|\s*title="(?P<title>[^"]*)"\s*\|\s*playlist="(?P<playlist>[^"]*)"""  # noqa: E501
    )

    # --- engine STREAM_START parsing (robust, with optional docker timestamp prefix) ---
    _RE_STREAM_START = re.compile(r"\bBUS\s+STREAM_START\b.*\bsrc=playbin\b", re.IGNORECASE)

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
            # IMPORTANT: timestamps=True adds a docker timestamp prefix.
            # We keep it because it's useful for debugging; parsers must tolerate it.
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
    def _parse_sched_ts(ts: str) -> Optional[dt.datetime]:
        """Parse scheduler log timestamp 'YYYY-MM-DD HH:MM:SS,mmm' as naive datetime."""
        try:
            return dt.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S,%f")
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

    # ----------------------- Normalization helpers (scheduler ↔ icecast matching) -----------------------

    @staticmethod
    def normalize_title(s: str) -> str:
        """Normalize titles so scheduler 'vanzo_-_me_and_you' can match Icecast 'Vanzo - Me And You'."""
        if not s:
            return ""
        s = s.strip()
        s = os.path.basename(s)
        s = re.sub(r"\.(mp3|wav|flac|ogg|m4a|aac)$", "", s, flags=re.IGNORECASE)
        s = s.replace("_-_", " - ")
        s = s.replace("_", " ")
        s = re.sub(r"\s+", " ", s).strip().lower()
        return s

    @staticmethod
    def display_title(s: str) -> str:
        """Human display helper for scheduler titles (slugified or already human)."""
        if not s:
            return ""
        s = s.strip()
        s = os.path.basename(s)
        s = re.sub(r"\.(mp3|wav|flac|ogg|m4a|aac)$", "", s, flags=re.IGNORECASE)
        s = s.replace("_-_", " - ")
        s = s.replace("_", " ")
        s = re.sub(r"\s+", " ", s).strip()
        return s

    # ----------------------- Engine preprocess (compat) -----------------------

    def _clean_preprocess_title(self, rest: str) -> Optional[str]:
        """Convert 'preprocess:' payload into a clean 'Artist - Title' string."""
        s = (rest or "").strip()
        if not s:
            return None

        s = self._RE_LEADING_IDX.sub("", s).strip()

        if "->" in s:
            left = s.split("->", 1)[0].strip()
            s = left

        s = self._RE_PAREN_TRAIL.sub("", s).strip()
        s = os.path.basename(s)
        s = self._RE_EXT.sub("", s).strip()

        s = s.replace("_-_", " - ")
        s = s.replace("_", " ")
        s = re.sub(r"\s+", " ", s).strip()

        return s or None

    def extract_preprocess_titles(self, engine_container: str, tail: int = 2500) -> Dict[str, Any]:
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

    # ----------------------- Scheduler NEXT (fixed) -----------------------

    @staticmethod
    def _strip_docker_prefix(line: str) -> str:
        """Remove optional docker timestamp prefix if present."""
        return DockerClient._RE_DOCKER_TS_PREFIX.sub("", line, count=1).strip()

    def extract_scheduler_next_entries(self, scheduler_container: str, tail: int = 2500) -> Dict[str, Any]:
        txt = self.tail_logs(scheduler_container, tail=tail)
        if not txt or txt.startswith("[control]"):
            return {
                "ok": False,
                "source": "scheduler_logs",
                "scheduler_container": scheduler_container,
                "error": txt.strip() if txt else "empty logs",
                "entries": [],
            }

        entries: List[NextEntry] = []
        for raw in txt.splitlines():
            line = self._strip_docker_prefix(raw)
            m = self._RE_SCHED_NEXT.search(line)  # search, not match
            if not m:
                continue
            ts_raw = m.group("ts") or ""
            title_raw = m.group("title") or ""
            playlist = m.group("playlist") or ""
            title_norm = self.normalize_title(title_raw)
            entries.append(
                NextEntry(
                    ts_raw=ts_raw,
                    ts=self._parse_sched_ts(ts_raw),
                    title_raw=title_raw,
                    title_norm=title_norm,
                    playlist=playlist,
                )
            )

        return {
            "ok": True,
            "source": "scheduler_logs",
            "scheduler_container": scheduler_container,
            "count": len(entries),
            "entries": [
                {
                    "ts": e.ts_raw,
                    "title": e.title_raw,
                    "title_norm": e.title_norm,
                    "title_display": self.display_title(e.title_raw),
                    "playlist": e.playlist,
                }
                for e in entries
            ],
        }

    def infer_playlist_for_title_from_scheduler(
        self,
        scheduler_container: str,
        current_title: Optional[str],
        tail: int = 2500,
    ) -> Dict[str, Any]:
        cur_norm = self.normalize_title(current_title or "")
        data = self.extract_scheduler_next_entries(scheduler_container, tail=tail)
        if not data.get("ok"):
            return {"ok": False, "error": data.get("error"), "playlist": None, "match": None}

        entries = data.get("entries") or []
        if not cur_norm or not entries:
            return {"ok": True, "playlist": None, "match": None, "current_title": current_title, "current_norm": cur_norm}

        match = None
        for e in reversed(entries):
            if (e.get("title_norm") or "") == cur_norm:
                match = e
                break

        if not match:
            return {"ok": True, "playlist": None, "match": None, "current_title": current_title, "current_norm": cur_norm}

        return {
            "ok": True,
            "playlist": match.get("playlist"),
            "match": match,
            "current_title": current_title,
            "current_norm": cur_norm,
        }

    def compute_upcoming_from_scheduler_next(
        self,
        scheduler_container: str,
        current_title: Optional[str],
        n: int = 10,
        tail: int = 2500,
    ) -> Dict[str, Any]:
        cur_norm = self.normalize_title(current_title or "")
        data = self.extract_scheduler_next_entries(scheduler_container, tail=tail)
        if not data.get("ok"):
            return {"ok": False, "error": data.get("error"), "upcoming": [], "source": "scheduler_logs"}

        raw_entries = data.get("entries") or []
        if not raw_entries:
            return {"ok": False, "error": "no scheduler NEXT entries found", "upcoming": [], "source": "scheduler_logs"}

        start_idx = None
        if cur_norm:
            for i in range(len(raw_entries) - 1, -1, -1):
                if (raw_entries[i].get("title_norm") or "") == cur_norm:
                    start_idx = i + 1
                    break

        seq = raw_entries[start_idx:] if start_idx is not None else raw_entries[-(n * 8) :]

        seen: set[str] = set()
        out: List[Dict[str, Any]] = []
        for e in seq:
            tn = (e.get("title_norm") or "").strip()
            if not tn or tn in seen:
                continue
            seen.add(tn)
            out.append(
                {
                    "title": e.get("title"),
                    "title_display": e.get("title_display") or self.display_title(str(e.get("title") or "")),
                    "playlist": e.get("playlist"),
                    "ts": e.get("ts"),
                }
            )
            if len(out) >= n:
                break

        return {
            "ok": True,
            "source": "scheduler_logs_after_current" if start_idx is not None else "scheduler_logs_fallback_tail",
            "current_title_found": start_idx is not None,
            "current_title": current_title,
            "upcoming": out,
        }

    # ----------------------- Engine STREAM_START (fixed) -----------------------

    def last_engine_stream_start(
        self,
        engine_container: str,
        tail: int = 800,
        recent_window_s: int = 10,
    ) -> Dict[str, Any]:
        txt = self.tail_logs(engine_container, tail=tail)
        if not txt or txt.startswith("[control]"):
            return {
                "ok": False,
                "source": "engine_logs",
                "engine_container": engine_container,
                "error": txt.strip() if txt else "empty logs",
                "line": None,
                "recent": False,
            }

        last_line = None
        last_ts = None

        for raw in txt.splitlines():
            line = self._strip_docker_prefix(raw)
            if not self._RE_STREAM_START.search(line):
                continue
            last_line = line.strip()
            m = re.match(r"^(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\s+", last_line)
            if m:
                last_ts = self._parse_sched_ts(m.group("ts"))

        if not last_line:
            return {
                "ok": True,
                "source": "engine_logs",
                "engine_container": engine_container,
                "line": None,
                "recent": False,
            }

        recent = False
        age_s = None
        if last_ts:
            try:
                now_local = dt.datetime.now()
                age_s = int((now_local - last_ts).total_seconds())
                recent = age_s >= 0 and age_s <= int(recent_window_s)
            except Exception:
                recent = False

        return {
            "ok": True,
            "source": "engine_logs",
            "engine_container": engine_container,
            "line": last_line,
            "ts": last_ts.isoformat() if last_ts else None,
            "age_s": age_s,
            "recent": recent,
            "recent_window_s": int(recent_window_s),
        }
