from __future__ import annotations

import ast
import datetime as dt
import os
import re
import shlex
import subprocess
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


@dataclass(frozen=True)
class TempoAcceptEntry:
    ts_raw: str
    ts: Optional[dt.datetime]
    a_title: str
    a_norm: str
    b_title: str
    b_norm: str
    delta_pct: Optional[float]
    max_delta_pct: Optional[float]
    attempt: Optional[str]


class DockerClient:
    """Docker wrapper for control-plane introspection + controlled ops."""

    _RE_PREPROCESS = re.compile(r"\bpreprocess:\s*(?P<rest>.+?)\s*$", re.IGNORECASE)
    _RE_LEADING_IDX = re.compile(r"^\s*\d+\s*[\.\)]\s*")
    _RE_PAREN_TRAIL = re.compile(r"\s*\(.*\)\s*$")
    _RE_EXT = re.compile(r"\.(mp3|wav|flac|ogg|m4a|aac)\s*$", re.IGNORECASE)

    _RE_DOCKER_TS_PREFIX = re.compile(r"^\s*\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+")

    _RE_SCHED_NEXT = re.compile(
        r"""(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\s+.*?\bazurmixd\.scheduler\b.*?\bNEXT\s*\|\s*title="(?P<title>[^"]*)"\s*\|\s*playlist="(?P<playlist>[^"]*)"""
    )

    _RE_STREAM_START = re.compile(r"\bBUS\s+STREAM_START\b.*\bsrc=playbin\b", re.IGNORECASE)
    _RE_LOG_TS = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\s+")
    _RE_DELTA_PCT = re.compile(r"\bdelta_pct=(?P<value>-?\d+(?:\.\d+)?)\b", re.IGNORECASE)
    _RE_MAX_DELTA_PCT = re.compile(r"\bmax_delta_pct=(?P<value>-?\d+(?:\.\d+)?)\b", re.IGNORECASE)
    _RE_ATTEMPT = re.compile(r"\battempt=(?P<value>\d+/\d+)\b", re.IGNORECASE)

    _RE_TEMPO_SELECT_OK_META = re.compile(
        r"""\btempo\(select(?::first)?\):\s*ok=True\b.*?\bmeta=(?P<meta>\{.*\})\s*$""",
        re.IGNORECASE,
    )
    _RE_TEMPO_SELECT_OK_REL = re.compile(
        r"""\btempo\(select\):\s*ok=True\b.*?\brel=(?P<rel>[^\s]+)""",
        re.IGNORECASE,
    )
    _RE_TEMPO_SELECT_ANY_META = re.compile(
        r"""\btempo\(select(?::first)?\):\s*ok=(?P<ok>True|False)\b.*?\bmeta=(?P<meta>\{.*\})\s*$""",
        re.IGNORECASE,
    )
    _RE_TEMPO_EXHAUST_FAIL_OPEN = re.compile(
        r"""\btempo\(packchain\):\s*EXHAUST\s*->\s*FAIL-OPEN\b""",
        re.IGNORECASE,
    )
    _RE_AFT_SET_URI = re.compile(
        r"""\bAFT#(?P<aft>\d+)\s+set_uri\s+ok\s+uri=(?P<uri>\S+)""",
        re.IGNORECASE,
    )
    _RE_PACK_URI_STAGE = re.compile(
        r"""(?:^|/)pack_(?P<packid>[a-f0-9]+)_(?P<stage>a|b|bridge)\.wav$""",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self.client = docker.from_env()
        self._host_cpu_prev_total: Optional[int] = None
        self._host_cpu_prev_idle: Optional[int] = None

    # ----------------------- Low-level ops: docker compose execution -----------------------

    @staticmethod
    def _run_cmd(cmd: List[str], cwd: str, timeout_s: int = 180) -> Dict[str, Any]:
        start = dt.datetime.now(dt.timezone.utc)
        try:
            p = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
            end = dt.datetime.now(dt.timezone.utc)
            return {
                "ok": p.returncode == 0,
                "rc": p.returncode,
                "cmd": " ".join(shlex.quote(x) for x in cmd),
                "cwd": cwd,
                "stdout": (p.stdout or "").strip(),
                "stderr": (p.stderr or "").strip(),
                "started_utc": start.isoformat(),
                "ended_utc": end.isoformat(),
                "duration_ms": int((end - start).total_seconds() * 1000),
            }
        except subprocess.TimeoutExpired as e:
            end = dt.datetime.now(dt.timezone.utc)
            return {
                "ok": False,
                "rc": 124,
                "cmd": " ".join(shlex.quote(x) for x in cmd),
                "cwd": cwd,
                "stdout": ((e.stdout or "") if isinstance(e.stdout, str) else "").strip(),
                "stderr": ((e.stderr or "") if isinstance(e.stderr, str) else "").strip() or f"timeout after {timeout_s}s",
                "started_utc": start.isoformat(),
                "ended_utc": end.isoformat(),
                "duration_ms": int((end - start).total_seconds() * 1000),
            }
        except Exception as e:
            end = dt.datetime.now(dt.timezone.utc)
            return {
                "ok": False,
                "rc": 127,
                "cmd": " ".join(shlex.quote(x) for x in cmd),
                "cwd": cwd,
                "stdout": "",
                "stderr": f"exec error: {e}",
                "started_utc": start.isoformat(),
                "ended_utc": end.isoformat(),
                "duration_ms": int((end - start).total_seconds() * 1000),
            }

    def compose_down(self, azuramix_dir: str) -> Dict[str, Any]:
        return self._run_cmd(["docker", "compose", "down"], cwd=azuramix_dir)

    def compose_up(self, azuramix_dir: str) -> Dict[str, Any]:
        return self._run_cmd(["docker", "compose", "up", "-d"], cwd=azuramix_dir)

    def compose_recreate(self, azuramix_dir: str) -> Dict[str, Any]:
        return self._run_cmd(["docker", "compose", "up", "-d", "--force-recreate"], cwd=azuramix_dir)

    def compose_update(self, azuramix_dir: str, image_ref: str) -> Dict[str, Any]:
        step_down = self._run_cmd(["docker", "compose", "down"], cwd=azuramix_dir)
        step_image_rm = self._run_cmd(["docker", "image", "rm", "-f", image_ref], cwd=azuramix_dir)
        ok = bool(step_down.get("ok")) and bool(step_image_rm.get("ok") or step_image_rm.get("rc") == 0)
        return {
            "ok": ok,
            "step_down": step_down,
            "step_image_rm": step_image_rm,
            "image_ref": image_ref,
        }

    # ----------------------- Docker info -----------------------

    def _get_container(self, name: str):
        try:
            return self.client.containers.get(name)
        except NotFound:
            return None
        except DockerException:
            return None

    @staticmethod
    def _parse_dt(v: Optional[str]) -> Optional[dt.datetime]:
        if not v:
            return None
        try:
            return dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return None

    def inspect_container(self, name: str) -> Dict[str, Any]:
        c = self._get_container(name)
        if c is None:
            return {"present": False, "name": name}

        attrs = getattr(c, "attrs", {}) or {}
        state = attrs.get("State", {}) or {}
        config = attrs.get("Config", {}) or {}

        created = attrs.get("Created")
        started = state.get("StartedAt")
        now = dt.datetime.now(dt.timezone.utc)

        created_dt = self._parse_dt(created)
        started_dt = self._parse_dt(started)

        age_s = None
        uptime_s = None
        if created_dt:
            age_s = int((now - created_dt).total_seconds())
        if started_dt and state.get("Running"):
            uptime_s = int((now - started_dt).total_seconds())

        health = None
        if isinstance(state.get("Health"), dict):
            health = state["Health"].get("Status")

        image = ""
        try:
            image = str(config.get("Image") or getattr(c.image, "tags", [""])[0] or "")
        except Exception:
            image = str(config.get("Image") or "")

        return {
            "present": True,
            "name": name,
            "id": getattr(c, "short_id", None),
            "image": image,
            "status": state.get("Status") or getattr(c, "status", None),
            "created_at": created,
            "started_at": started,
            "running": bool(state.get("Running")),
            "restarting": bool(state.get("Restarting")),
            "paused": bool(state.get("Paused")),
            "dead": bool(state.get("Dead")),
            "health": health,
            "age_s": age_s,
            "uptime_s": uptime_s,
        }

    def runtime_summary(self, engine_container: str, scheduler_container: str) -> Dict[str, Any]:
        try:
            self.client.ping()
            docker_ping = True
        except Exception:
            docker_ping = False

        now = dt.datetime.now(dt.timezone.utc).isoformat()

        return {
            "now_utc": now,
            "docker_ping": docker_ping,
            "engine": self.inspect_container(engine_container),
            "scheduler": self.inspect_container(scheduler_container),
        }

    # ----------------------- Logs -----------------------

    def tail_logs(self, name: str, tail: int = 400) -> str:
        c = self._get_container(name)
        if c is None:
            return f"[control] container not found: {name}"
        try:
            raw = c.logs(tail=tail, stdout=True, stderr=True, timestamps=True)
            if isinstance(raw, bytes):
                return raw.decode("utf-8", errors="replace")
            return str(raw)
        except Exception as e:
            return f"[control] log read error for {name}: {e}"

    # ----------------------- Host resources -----------------------

    @staticmethod
    def _read_proc_stat() -> Optional[Tuple[int, int]]:
        try:
            with open("/proc/stat", "r", encoding="utf-8") as f:
                line = f.readline().strip()
            if not line.startswith("cpu "):
                return None
            parts = [int(x) for x in line.split()[1:]]
            if len(parts) < 4:
                return None
            idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
            total = sum(parts)
            return total, idle
        except Exception:
            return None

    def _sample_host_cpu_percent(self) -> Optional[float]:
        snap1 = self._read_proc_stat()
        if snap1 is None:
            return None

        prev_total = self._host_cpu_prev_total
        prev_idle = self._host_cpu_prev_idle

        self._host_cpu_prev_total, self._host_cpu_prev_idle = snap1

        if prev_total is None or prev_idle is None:
            time.sleep(0.08)
            snap2 = self._read_proc_stat()
            if snap2 is None:
                return None
            totald = snap2[0] - snap1[0]
            idled = snap2[1] - snap1[1]
            if totald <= 0:
                return None
            return round(100.0 * (1.0 - (idled / totald)), 2)

        totald = snap1[0] - prev_total
        idled = snap1[1] - prev_idle
        if totald <= 0:
            return None
        return round(100.0 * (1.0 - (idled / totald)), 2)

    @staticmethod
    def _read_loadavg() -> Dict[str, Optional[float]]:
        try:
            one, five, fifteen = os.getloadavg()
            return {
                "one": round(float(one), 2),
                "five": round(float(five), 2),
                "fifteen": round(float(fifteen), 2),
            }
        except Exception:
            return {"one": None, "five": None, "fifteen": None}

    @staticmethod
    def _read_meminfo() -> Dict[str, Optional[int]]:
        data: Dict[str, int] = {}
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if ":" not in line:
                        continue
                    k, v = line.split(":", 1)
                    raw = v.strip().split()[0]
                    data[k] = int(raw) * 1024
        except Exception:
            return {
                "total_bytes": None,
                "available_bytes": None,
                "used_bytes": None,
                "cached_bytes": None,
                "used_percent": None,
            }

        total = data.get("MemTotal")
        available = data.get("MemAvailable")
        cached = data.get("Cached", 0) + data.get("Buffers", 0)
        used = None
        used_percent = None
        if total is not None and available is not None:
            used = max(total - available, 0)
            if total > 0:
                used_percent = round((used / total) * 100.0, 2)

        return {
            "total_bytes": total,
            "available_bytes": available,
            "used_bytes": used,
            "cached_bytes": cached,
            "used_percent": used_percent,
        }

    def host_resources_summary(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "source": "host_procfs",
            "now_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "cpu": {
                "percent": self._sample_host_cpu_percent(),
                "sample": "proc/stat",
            },
            "memory": self._read_meminfo(),
            "loadavg": self._read_loadavg(),
        }

    # ----------------------- Title normalization / display -----------------------

    @staticmethod
    def _coerce_rel_title(rel: str) -> Optional[str]:
        s = (rel or "").strip()
        if not s:
            return None
        s = os.path.basename(s)
        s = DockerClient._RE_EXT.sub("", s).strip()
        s = s.replace("_-_", " - ")
        s = s.replace("_", " ")
        s = re.sub(r"\s+", " ", s).strip()
        return s or None

    @staticmethod
    def display_title(s: str) -> str:
        t = (s or "").strip()
        if not t:
            return ""
        t = os.path.basename(t)
        t = DockerClient._RE_EXT.sub("", t).strip()
        t = t.replace("_-_", " - ")
        t = t.replace("_", " ")
        t = re.sub(r"\s+", " ", t).strip()
        return t

    @staticmethod
    def normalize_title(s: str) -> str:
        t = DockerClient.display_title(s).lower().strip()
        t = re.sub(r"\[[^\]]*\]", "", t)
        t = re.sub(r"\([^)]*\)", "", t)
        t = re.sub(r"[^a-z0-9]+", "", t)
        return t

    @staticmethod
    def _dedupe_keep_order(items: List[str]) -> List[str]:
        out: List[str] = []
        seen: set[str] = set()
        for x in items:
            n = DockerClient.normalize_title(x)
            if not n or n in seen:
                continue
            seen.add(n)
            out.append(DockerClient.display_title(x))
        return out

    # ----------------------- Playback parsing -----------------------

    @staticmethod
    def _playback_title_from_uri(raw: str) -> Optional[str]:
        if not raw:
            return None
        try:
            parsed = urllib.parse.urlparse(raw)
            path = urllib.parse.unquote(parsed.path or "")
        except Exception:
            path = raw
        return DockerClient._coerce_rel_title(path)

    @classmethod
    def _playback_state_from_uri(cls, raw: str) -> Dict[str, Any]:
        path = ""
        if raw:
            try:
                parsed = urllib.parse.urlparse(raw)
                path = urllib.parse.unquote(parsed.path or "")
            except Exception:
                path = raw

        m_pack = cls._RE_PACK_URI_STAGE.search(path or "")
        if m_pack:
            stage = (m_pack.group("stage") or "").lower()
            pack_id = (m_pack.group("packid") or "").lower() or None
            return {
                "playback_uri": raw or None,
                "playback_path": path or None,
                "playback_stage": stage,
                "pack_id": pack_id,
                "playback_title": None,
            }

        title = cls._playback_title_from_uri(raw)
        return {
            "playback_uri": raw or None,
            "playback_path": path or None,
            "playback_stage": "direct" if title else ("silence" if "azurmixd_silence.mp3" in path else "unknown"),
            "pack_id": None,
            "playback_title": title,
        }

    def extract_tempo_selected_titles(self, engine_container: str, tail: int = 2500) -> Dict[str, Any]:
        txt = self.tail_logs(engine_container, tail=tail)
        if not txt or txt.startswith("[control]"):
            return {
                "ok": False,
                "source": "engine_logs_tempo",
                "engine_container": engine_container,
                "error": txt.strip() if txt else "empty logs",
                "titles": [],
            }

        titles: List[str] = []
        for raw in txt.splitlines():
            line = self._strip_docker_prefix(raw)

            m_meta = self._RE_TEMPO_SELECT_OK_META.search(line)
            if m_meta:
                try:
                    meta = ast.literal_eval((m_meta.group("meta") or "").strip())
                except Exception:
                    meta = None
                if isinstance(meta, dict):
                    t = self._coerce_rel_title(str(meta.get("b_rel") or ""))
                    if t:
                        titles.append(t)
                        continue

            m_rel = self._RE_TEMPO_SELECT_OK_REL.search(line)
            if m_rel:
                t = self._coerce_rel_title(m_rel.group("rel") or "")
                if t:
                    titles.append(t)

        return {
            "ok": True,
            "source": "engine_logs_tempo",
            "engine_container": engine_container,
            "titles": titles,
            "count": len(titles),
        }

    def extract_tempo_runtime_state(self, engine_container: str, tail: int = 2500) -> Dict[str, Any]:
        txt = self.tail_logs(engine_container, tail=tail)
        if not txt or txt.startswith("[control]"):
            return {
                "ok": False,
                "source": "engine_logs_tempo_runtime",
                "engine_container": engine_container,
                "error": txt.strip() if txt else "empty logs",
                "current_title": None,
                "next_title": None,
                "current_bpm": None,
                "next_bpm": None,
                "playback_stage": None,
                "playback_uri": None,
                "playback_title": None,
            }

        last_state: Optional[Dict[str, Any]] = None
        last_state_idx = -1
        last_playback: Optional[Dict[str, Any]] = None
        last_playback_idx = -1

        for idx, raw in enumerate(txt.splitlines()):
            line = self._strip_docker_prefix(raw)

            m_any = self._RE_TEMPO_SELECT_ANY_META.search(line)
            if m_any:
                try:
                    meta = ast.literal_eval((m_any.group("meta") or "").strip())
                except Exception:
                    meta = None

                if isinstance(meta, dict):
                    last_state = {
                        "ok": True,
                        "source": "engine_logs_tempo_runtime",
                        "engine_container": engine_container,
                        "decision_ok": str(m_any.group("ok") or "").lower() == "true",
                        "fail_open": False,
                        "current_title": self._coerce_rel_title(str(meta.get("a_rel") or "")),
                        "next_title": self._coerce_rel_title(str(meta.get("b_rel") or "")),
                        "current_bpm": self._bpm_or_none(meta.get("a")),
                        "next_bpm": self._bpm_or_none(meta.get("b")),
                        "a_src": meta.get("a_src"),
                        "b_src": meta.get("b_src"),
                        "a_fx": meta.get("a_fx"),
                        "b_fx": meta.get("b_fx"),
                        "a_tid": meta.get("a_tid"),
                        "b_tid": meta.get("b_tid"),
                        "raw_meta": meta,
                    }
                    last_state_idx = idx
                    continue

            if self._RE_TEMPO_EXHAUST_FAIL_OPEN.search(line):
                if last_state:
                    last_state["fail_open"] = True
                    last_state["decision_ok"] = True
                continue

            m_uri = self._RE_AFT_SET_URI.search(line)
            if m_uri:
                playback = self._playback_state_from_uri(m_uri.group("uri") or "")
                playback["aft"] = int(m_uri.group("aft"))
                last_playback = playback
                last_playback_idx = idx
                continue

        if last_state is None:
            return {
                "ok": False,
                "source": "engine_logs_tempo_runtime",
                "engine_container": engine_container,
                "error": "no tempo(select) state found in logs",
                "current_title": None,
                "next_title": None,
                "current_bpm": None,
                "next_bpm": None,
                "playback_stage": (last_playback or {}).get("playback_stage"),
                "playback_uri": (last_playback or {}).get("playback_uri"),
                "playback_title": (last_playback or {}).get("playback_title"),
            }

        merged = dict(last_state)

        if last_playback and last_playback_idx >= last_state_idx:
            merged.update(
                {
                    "playback_stage": last_playback.get("playback_stage"),
                    "playback_uri": last_playback.get("playback_uri"),
                    "playback_path": last_playback.get("playback_path"),
                    "playback_title": last_playback.get("playback_title"),
                    "playback_pack_id": last_playback.get("pack_id"),
                    "playback_aft": last_playback.get("aft"),
                }
            )
        else:
            merged.update(
                {
                    "playback_stage": None,
                    "playback_uri": None,
                    "playback_path": None,
                    "playback_title": None,
                    "playback_pack_id": None,
                    "playback_aft": None,
                }
            )

        return merged

    # ----------------------- tempo(select) accepted entries -----------------------

    @staticmethod
    def _parse_sched_ts(v: str) -> Optional[dt.datetime]:
        s = (v or "").strip()
        if not s:
            return None
        try:
            return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S,%f")
        except Exception:
            return None

    @staticmethod
    def _extract_log_ts_raw(line: str) -> Optional[str]:
        m = DockerClient._RE_LOG_TS.search(line or "")
        return (m.group("ts") or "").strip() or None if m else None

    @staticmethod
    def _bpm_or_none(v: Any) -> Optional[float]:
        try:
            f = float(v)
            return round(f, 2) if f > 0 else None
        except Exception:
            return None

    @staticmethod
    def _extract_float_from_line(rx: re.Pattern[str], line: str) -> Optional[float]:
        m = rx.search(line or "")
        if not m:
            return None
        try:
            return round(float(m.group("value")), 2)
        except Exception:
            return None

    @staticmethod
    def _extract_attempt_from_line(line: str) -> Optional[str]:
        m = DockerClient._RE_ATTEMPT.search(line or "")
        return str(m.group("value") or "").strip() or None if m else None

    def extract_tempo_accept_entries(self, engine_container: str, tail: int = 3000) -> Dict[str, Any]:
        txt = self.tail_logs(engine_container, tail=tail)
        if not txt or txt.startswith("[control]"):
            return {
                "ok": False,
                "source": "engine_logs_tempo_accept",
                "engine_container": engine_container,
                "error": txt.strip() if txt else "empty logs",
                "entries": [],
            }

        entries: List[TempoAcceptEntry] = []
        for raw in txt.splitlines():
            line = self._strip_docker_prefix(raw)

            m_meta = self._RE_TEMPO_SELECT_OK_META.search(line)
            if not m_meta:
                continue

            try:
                meta = ast.literal_eval((m_meta.group("meta") or "").strip())
            except Exception:
                meta = None
            if not isinstance(meta, dict):
                continue

            a_title = self._coerce_rel_title(str(meta.get("a_rel") or "")) or ""
            b_title = self._coerce_rel_title(str(meta.get("b_rel") or "")) or ""
            if not a_title or not b_title:
                continue

            ts_raw = self._extract_log_ts_raw(line)
            entries.append(
                TempoAcceptEntry(
                    ts_raw=ts_raw,
                    ts=self._parse_sched_ts(ts_raw) if ts_raw else None,
                    a_title=a_title,
                    a_norm=self.normalize_title(a_title),
                    b_title=b_title,
                    b_norm=self.normalize_title(b_title),
                    delta_pct=self._extract_float_from_line(self._RE_DELTA_PCT, line),
                    max_delta_pct=self._extract_float_from_line(self._RE_MAX_DELTA_PCT, line),
                    attempt=self._extract_attempt_from_line(line),
                )
            )

        return {
            "ok": True,
            "source": "engine_logs_tempo_accept",
            "engine_container": engine_container,
            "count": len(entries),
            "entries": [
                {
                    "ts": e.ts_raw,
                    "a_title": e.a_title,
                    "a_norm": e.a_norm,
                    "b_title": e.b_title,
                    "b_norm": e.b_norm,
                    "delta_pct": e.delta_pct,
                    "max_delta_pct": e.max_delta_pct,
                    "attempt": e.attempt,
                }
                for e in entries
            ],
        }

    def compute_upcoming_from_tempo_accepts(
        self,
        engine_container: str,
        current_title: Optional[str],
        n: int = 10,
        tail: int = 3000,
    ) -> Dict[str, Any]:
        cur_norm = self.normalize_title(current_title or "")
        data = self.extract_tempo_accept_entries(engine_container, tail=tail)
        if not data.get("ok"):
            return {
                "ok": False,
                "error": data.get("error"),
                "upcoming": [],
                "source": "engine_logs_tempo_accept",
            }

        raw_entries = data.get("entries") or []
        if not raw_entries:
            return {
                "ok": False,
                "error": "no accepted tempo(select) entries found",
                "upcoming": [],
                "source": "engine_logs_tempo_accept",
            }

        if not cur_norm:
            return {
                "ok": True,
                "source": "engine_logs_tempo_accept_waiting_for_current",
                "current_title_found": False,
                "current_title": current_title,
                "upcoming": [],
                "entries_considered": 0,
            }

        start_idx: Optional[int] = None

        for i in range(len(raw_entries) - 1, -1, -1):
            entry = raw_entries[i] or {}
            if (entry.get("a_norm") or "") == cur_norm:
                start_idx = i
                break

        if start_idx is None:
            for i in range(len(raw_entries) - 1, -1, -1):
                entry = raw_entries[i] or {}
                if (entry.get("b_norm") or "") == cur_norm:
                    start_idx = i + 1
                    break

        if start_idx is None:
            return {
                "ok": True,
                "source": "engine_logs_tempo_accept_unanchored",
                "current_title_found": False,
                "current_title": current_title,
                "upcoming": [],
                "entries_considered": 0,
            }

        seq = raw_entries[start_idx:]

        seen: set[str] = set()
        out: List[Dict[str, Any]] = []
        for entry in seq:
            b_norm = str(entry.get("b_norm") or "").strip()
            if not b_norm or b_norm == cur_norm or b_norm in seen:
                continue
            seen.add(b_norm)
            out.append(
                {
                    "title": entry.get("b_title"),
                    "title_display": self.display_title(str(entry.get("b_title") or "")),
                    "playlist": None,
                    "ts": entry.get("ts"),
                    "from_title": entry.get("a_title"),
                    "delta_pct": entry.get("delta_pct"),
                    "max_delta_pct": entry.get("max_delta_pct"),
                    "attempt": entry.get("attempt"),
                }
            )
            if len(out) >= n:
                break

        return {
            "ok": True,
            "source": "engine_logs_tempo_accept_after_current",
            "current_title_found": True,
            "current_title": current_title,
            "upcoming": out,
            "entries_considered": len(seq),
        }

    # ----------------------- Engine preprocess (compat) -----------------------

    def _clean_preprocess_title(self, rest: str) -> Optional[str]:
        s = (rest or "").strip()
        if not s:
            return None

        s = self._RE_LEADING_IDX.sub("", s).strip()

        if "->" in s:
            s = s.split("->", 1)[0].strip()

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
            return {"ok": False, "source": "engine_logs", "engine_container": engine_container, "error": txt.strip() if txt else "empty logs", "titles": []}

        titles: List[str] = []
        for line in txt.splitlines():
            m = self._RE_PREPROCESS.search(line)
            if not m:
                continue
            rest = (m.group("rest") or "").strip()
            t = self._clean_preprocess_title(rest)
            if t:
                titles.append(t)

        return {"ok": True, "source": "engine_logs", "engine_container": engine_container, "titles": titles, "count": len(titles)}

    def compute_upcoming_from_preprocess(self, engine_container: str, current_title: Optional[str], n: int = 10, tail: int = 2500) -> Dict[str, Any]:
        tempo_data = self.extract_tempo_selected_titles(engine_container, tail=tail)
        if tempo_data.get("ok"):
            tempo_titles = [t for t in (tempo_data.get("titles") or []) if isinstance(t, str) and t.strip()]
            if tempo_titles:
                cur_norm = self.normalize_title(current_title or "")
                start_idx = None

                if cur_norm:
                    for i in range(len(tempo_titles) - 1, -1, -1):
                        if self.normalize_title(tempo_titles[i]) == cur_norm:
                            start_idx = i + 1
                            break

                if start_idx is None:
                    chunk = self._dedupe_keep_order(tempo_titles[-(n * 4):])
                    return {
                        "ok": True,
                        "source": "engine_logs_tempo_fallback_tail",
                        "current_title_found": False,
                        "current_title": current_title,
                        "upcoming": chunk[:n],
                    }

                chunk2 = self._dedupe_keep_order(tempo_titles[start_idx:])
                return {
                    "ok": True,
                    "source": "engine_logs_tempo_after_current",
                    "current_title_found": True,
                    "current_title": current_title,
                    "upcoming": chunk2[:n],
                }

        data = self.extract_preprocess_titles(engine_container, tail=tail)
        if not data.get("ok"):
            return {"ok": False, "error": data.get("error"), "upcoming": [], "source": "engine_logs"}

        titles = [t for t in (data.get("titles") or []) if isinstance(t, str) and t.strip()]
        if not titles:
            return {"ok": False, "error": "no preprocess titles found", "upcoming": [], "source": "engine_logs"}

        cur_norm = self.normalize_title(current_title or "")
        start_idx = None

        if cur_norm:
            for i in range(len(titles) - 1, -1, -1):
                if self.normalize_title(titles[i]) == cur_norm:
                    start_idx = i + 1
                    break

        if start_idx is None:
            chunk = self._dedupe_keep_order(titles[-(n * 4):])
            return {
                "ok": True,
                "source": "engine_logs_preprocess_fallback_tail",
                "current_title_found": False,
                "current_title": current_title,
                "upcoming": chunk[:n],
            }

        chunk2 = self._dedupe_keep_order(titles[start_idx:])
        return {
            "ok": True,
            "source": "engine_logs_preprocess_after_current",
            "current_title_found": True,
            "current_title": current_title,
            "upcoming": chunk2[:n],
        }

    # ----------------------- Scheduler NEXT -----------------------

    @staticmethod
    def _strip_docker_prefix(line: str) -> str:
        return DockerClient._RE_DOCKER_TS_PREFIX.sub("", line, count=1).strip()

    def extract_scheduler_next_entries(self, scheduler_container: str, tail: int = 2500) -> Dict[str, Any]:
        txt = self.tail_logs(scheduler_container, tail=tail)
        if not txt or txt.startswith("[control]"):
            return {"ok": False, "source": "scheduler_logs", "scheduler_container": scheduler_container, "error": txt.strip() if txt else "empty logs", "entries": []}

        entries: List[NextEntry] = []
        for raw in txt.splitlines():
            line = self._strip_docker_prefix(raw)
            m = self._RE_SCHED_NEXT.search(line)
            if not m:
                continue
            ts_raw = m.group("ts") or ""
            title_raw = m.group("title") or ""
            playlist = m.group("playlist") or ""
            title_norm = self.normalize_title(title_raw)
            entries.append(NextEntry(ts_raw=ts_raw, ts=self._parse_sched_ts(ts_raw), title_raw=title_raw, title_norm=title_norm, playlist=playlist))

        return {
            "ok": True,
            "source": "scheduler_logs",
            "scheduler_container": scheduler_container,
            "count": len(entries),
            "entries": [
                {"ts": e.ts_raw, "title": e.title_raw, "title_norm": e.title_norm, "title_display": self.display_title(e.title_raw), "playlist": e.playlist}
                for e in entries
            ],
        }

    def infer_playlist_for_title_from_scheduler(self, scheduler_container: str, current_title: Optional[str], tail: int = 2500) -> Dict[str, Any]:
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

        return {"ok": True, "playlist": match.get("playlist"), "match": match, "current_title": current_title, "current_norm": cur_norm}

    def compute_upcoming_from_scheduler_next(self, scheduler_container: str, current_title: Optional[str], n: int = 10, tail: int = 2500) -> Dict[str, Any]:
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

        seq = raw_entries[start_idx:] if start_idx is not None else raw_entries[-(n * 8):]

        seen: set[str] = set()
        out: List[Dict[str, Any]] = []
        for e in seq:
            tn = (e.get("title_norm") or "").strip()
            if not tn or tn in seen:
                continue
            seen.add(tn)
            out.append({"title": e.get("title"), "title_display": e.get("title_display") or self.display_title(str(e.get("title") or "")), "playlist": e.get("playlist"), "ts": e.get("ts")})
            if len(out) >= n:
                break

        return {
            "ok": True,
            "source": "scheduler_logs_after_current" if start_idx is not None else "scheduler_logs_fallback_tail",
            "current_title_found": start_idx is not None,
            "current_title": current_title,
            "upcoming": out,
        }

    # ----------------------- Engine STREAM_START -----------------------

    def last_engine_stream_start(self, engine_container: str, tail: int = 800, recent_window_s: int = 10) -> Dict[str, Any]:
        txt = self.tail_logs(engine_container, tail=tail)
        if not txt or txt.startswith("[control]"):
            return {"ok": False, "source": "engine_logs", "engine_container": engine_container, "error": txt.strip() if txt else "empty logs", "line": None, "recent": False}

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
            return {"ok": True, "source": "engine_logs", "engine_container": engine_container, "line": None, "recent": False}

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
