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


@dataclass(frozen=True)
class TempoEvent:
    kind: str
    ts_raw: Optional[str]
    ts: Optional[dt.datetime]
    a_title: Optional[str]
    a_norm: str
    b_title: Optional[str]
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

    # ----------------------- Shared helpers -----------------------

    @staticmethod
    def _ok_or_error(txt: str, source: str, container_key: str, container_name: str) -> Optional[Dict[str, Any]]:
        if txt and not txt.startswith("[control]"):
            return None
        return {
            "ok": False,
            "source": source,
            container_key: container_name,
            "error": txt.strip() if txt else "empty logs",
        }

    @staticmethod
    def _parse_dt(v: Optional[str]) -> Optional[dt.datetime]:
        if not v:
            return None
        try:
            return dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def _parse_sched_ts(v: Optional[str]) -> Optional[dt.datetime]:
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

    @staticmethod
    def _bpm_or_none(v: Any) -> Optional[float]:
        try:
            f = float(v)
            return round(f, 2) if f > 0 else None
        except Exception:
            return None

    @staticmethod
    def _strip_docker_prefix(line: str) -> str:
        return DockerClient._RE_DOCKER_TS_PREFIX.sub("", line, count=1).strip()

    @staticmethod
    def _coerce_rel_title(rel: str) -> Optional[str]:
        s = (rel or "").strip()
        if not s:
            return None
        s = os.path.basename(s)
        s = DockerClient._RE_EXT.sub("", s).strip()
        s = s.replace("_-_", " - ").replace("_", " ")
        s = re.sub(r"\s+", " ", s).strip()
        return s or None

    @staticmethod
    def display_title(s: str) -> str:
        return DockerClient._coerce_rel_title(s) or ""

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

    def _iter_clean_log_lines(self, name: str, tail: int) -> Tuple[str, List[str]]:
        txt = self.tail_logs(name, tail=tail)
        return txt, [self._strip_docker_prefix(x) for x in txt.splitlines()] if txt else []

    @staticmethod
    def _anchor_index_for_current(events: List[TempoEvent], cur_norm: str) -> Tuple[Optional[int], bool]:
        for i in range(len(events) - 1, -1, -1):
            ev = events[i]
            if not isinstance(ev, TempoEvent) or ev.kind != "accept":
                continue
            if ev.a_norm == cur_norm:
                return i, True
            if ev.b_norm == cur_norm:
                return i + 1, False
        return None, False

    @staticmethod
    def _slice_from_current(
        items: List[Dict[str, Any]],
        current_norm: str,
        norm_key: str,
        n: int,
        fallback_mult: int,
        source_after: str,
        source_fallback: str,
        current_title: Optional[str],
    ) -> Dict[str, Any]:
        start_idx = None
        if current_norm:
            for i in range(len(items) - 1, -1, -1):
                if (items[i].get(norm_key) or "") == current_norm:
                    start_idx = i + 1
                    break

        seq = items[start_idx:] if start_idx is not None else items[-(n * fallback_mult):]
        out: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for e in seq:
            tn = (e.get(norm_key) or "").strip()
            if not tn or tn in seen:
                continue
            seen.add(tn)
            out.append(e)
            if len(out) >= n:
                break

        return {
            "ok": True,
            "source": source_after if start_idx is not None else source_fallback,
            "current_title_found": start_idx is not None,
            "current_title": current_title,
            "upcoming": out,
        }

    # ----------------------- Low-level ops: docker compose execution -----------------------

    @staticmethod
    def _run_cmd(cmd: List[str], cwd: str, timeout_s: int = 180) -> Dict[str, Any]:
        start = dt.datetime.now(dt.timezone.utc)
        base = {
            "cmd": " ".join(shlex.quote(x) for x in cmd),
            "cwd": cwd,
            "started_utc": start.isoformat(),
        }
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
                **base,
                "ok": p.returncode == 0,
                "rc": p.returncode,
                "stdout": (p.stdout or "").strip(),
                "stderr": (p.stderr or "").strip(),
                "ended_utc": end.isoformat(),
                "duration_ms": int((end - start).total_seconds() * 1000),
            }
        except subprocess.TimeoutExpired as e:
            end = dt.datetime.now(dt.timezone.utc)
            return {
                **base,
                "ok": False,
                "rc": 124,
                "stdout": ((e.stdout or "") if isinstance(e.stdout, str) else "").strip(),
                "stderr": ((e.stderr or "") if isinstance(e.stderr, str) else "").strip() or f"timeout after {timeout_s}s",
                "ended_utc": end.isoformat(),
                "duration_ms": int((end - start).total_seconds() * 1000),
            }
        except Exception as e:
            end = dt.datetime.now(dt.timezone.utc)
            return {
                **base,
                "ok": False,
                "rc": 127,
                "stdout": "",
                "stderr": f"exec error: {e}",
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
        return {
            "ok": bool(step_down.get("ok")) and bool(step_image_rm.get("ok") or step_image_rm.get("rc") == 0),
            "step_down": step_down,
            "step_image_rm": step_image_rm,
            "image_ref": image_ref,
        }

    # ----------------------- Docker info -----------------------

    def _get_container(self, name: str):
        try:
            return self.client.containers.get(name)
        except (NotFound, DockerException):
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
        age_s = int((now - created_dt).total_seconds()) if created_dt else None
        uptime_s = int((now - started_dt).total_seconds()) if started_dt and state.get("Running") else None
        health = state.get("Health", {}).get("Status") if isinstance(state.get("Health"), dict) else None

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

        return {
            "now_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
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
            return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
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
            return sum(parts), idle
        except Exception:
            return None

    def _sample_host_cpu_percent(self) -> Optional[float]:
        snap1 = self._read_proc_stat()
        if snap1 is None:
            return None

        prev_total, prev_idle = self._host_cpu_prev_total, self._host_cpu_prev_idle
        self._host_cpu_prev_total, self._host_cpu_prev_idle = snap1

        if prev_total is None or prev_idle is None:
            time.sleep(0.08)
            snap2 = self._read_proc_stat()
            if snap2 is None:
                return None
            totald, idled = snap2[0] - snap1[0], snap2[1] - snap1[1]
        else:
            totald, idled = snap1[0] - prev_total, snap1[1] - prev_idle

        if totald <= 0:
            return None
        return round(100.0 * (1.0 - (idled / totald)), 2)

    @staticmethod
    def _read_loadavg() -> Dict[str, Optional[float]]:
        try:
            one, five, fifteen = os.getloadavg()
            return {"one": round(float(one), 2), "five": round(float(five), 2), "fifteen": round(float(fifteen), 2)}
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
                    data[k] = int(v.strip().split()[0]) * 1024
        except Exception:
            return {
                "total_bytes": None,
                "available_bytes": None,
                "used_bytes": None,
                "cached_bytes": None,
                "used_percent": None,
            }

        total, available = data.get("MemTotal"), data.get("MemAvailable")
        cached = data.get("Cached", 0) + data.get("Buffers", 0)
        used = max(total - available, 0) if total is not None and available is not None else None
        used_percent = round((used / total) * 100.0, 2) if used is not None and total and total > 0 else None
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
            "cpu": {"percent": self._sample_host_cpu_percent(), "sample": "proc/stat"},
            "memory": self._read_meminfo(),
            "loadavg": self._read_loadavg(),
        }

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
            return {
                "playback_uri": raw or None,
                "playback_path": path or None,
                "playback_stage": (m_pack.group("stage") or "").lower(),
                "pack_id": (m_pack.group("packid") or "").lower() or None,
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

    # ----------------------- Tempo parsing -----------------------

    def extract_tempo_selected_titles(self, engine_container: str, tail: int = 2500) -> Dict[str, Any]:
        txt, lines = self._iter_clean_log_lines(engine_container, tail)
        err = self._ok_or_error(txt, "engine_logs_tempo", "engine_container", engine_container)
        if err:
            return {**err, "titles": []}

        titles: List[str] = []
        for line in lines:
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
        txt, lines = self._iter_clean_log_lines(engine_container, tail)
        err = self._ok_or_error(txt, "engine_logs_tempo_runtime", "engine_container", engine_container)
        if err:
            return {
                **err,
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

        for idx, line in enumerate(lines):
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
                last_playback = self._playback_state_from_uri(m_uri.group("uri") or "")
                last_playback["aft"] = int(m_uri.group("aft"))
                last_playback_idx = idx

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
        playback = last_playback if last_playback and last_playback_idx >= last_state_idx else {}
        merged.update(
            {
                "playback_stage": playback.get("playback_stage"),
                "playback_uri": playback.get("playback_uri"),
                "playback_path": playback.get("playback_path"),
                "playback_title": playback.get("playback_title"),
                "playback_pack_id": playback.get("pack_id"),
                "playback_aft": playback.get("aft"),
            }
        )
        return merged

    def extract_tempo_event_stream(self, engine_container: str, tail: int = 3000) -> Dict[str, Any]:
        txt, lines = self._iter_clean_log_lines(engine_container, tail)
        err = self._ok_or_error(txt, "engine_logs_tempo_event_stream", "engine_container", engine_container)
        if err:
            return {**err, "events": []}

        events: List[TempoEvent] = []
        for line in lines:
            ts_raw = self._extract_log_ts_raw(line)
            ts = self._parse_sched_ts(ts_raw) if ts_raw else None

            m_meta = self._RE_TEMPO_SELECT_OK_META.search(line)
            if m_meta:
                try:
                    meta = ast.literal_eval((m_meta.group("meta") or "").strip())
                except Exception:
                    meta = None
                if isinstance(meta, dict):
                    a_title = self._coerce_rel_title(str(meta.get("a_rel") or ""))
                    b_title = self._coerce_rel_title(str(meta.get("b_rel") or ""))
                    if a_title and b_title:
                        events.append(
                            TempoEvent(
                                kind="accept",
                                ts_raw=ts_raw,
                                ts=ts,
                                a_title=a_title,
                                a_norm=self.normalize_title(a_title),
                                b_title=b_title,
                                b_norm=self.normalize_title(b_title),
                                delta_pct=self._extract_float_from_line(self._RE_DELTA_PCT, line),
                                max_delta_pct=self._extract_float_from_line(self._RE_MAX_DELTA_PCT, line),
                                attempt=self._extract_attempt_from_line(line),
                            )
                        )
                        continue

            if self._RE_TEMPO_EXHAUST_FAIL_OPEN.search(line):
                events.append(
                    TempoEvent(
                        kind="fail_open",
                        ts_raw=ts_raw,
                        ts=ts,
                        a_title=None,
                        a_norm="",
                        b_title=None,
                        b_norm="",
                        delta_pct=None,
                        max_delta_pct=None,
                        attempt=None,
                    )
                )

        return {
            "ok": True,
            "source": "engine_logs_tempo_event_stream",
            "engine_container": engine_container,
            "count": len(events),
            "events": events,
        }

    def extract_tempo_accept_entries(self, engine_container: str, tail: int = 3000) -> Dict[str, Any]:
        data = self.extract_tempo_event_stream(engine_container, tail=tail)
        if not data.get("ok"):
            return {
                "ok": False,
                "source": "engine_logs_tempo_accept",
                "engine_container": engine_container,
                "error": data.get("error"),
                "entries": [],
            }

        entries: List[TempoAcceptEntry] = []
        for ev in data.get("events") or []:
            if not isinstance(ev, TempoEvent) or ev.kind != "accept":
                continue
            entries.append(
                TempoAcceptEntry(
                    ts_raw=ev.ts_raw or "",
                    ts=ev.ts,
                    a_title=ev.a_title or "",
                    a_norm=ev.a_norm,
                    b_title=ev.b_title or "",
                    b_norm=ev.b_norm,
                    delta_pct=ev.delta_pct,
                    max_delta_pct=ev.max_delta_pct,
                    attempt=ev.attempt,
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
        data = self.extract_tempo_event_stream(engine_container, tail=tail)
        if not data.get("ok"):
            return {"ok": False, "error": data.get("error"), "upcoming": [], "source": "engine_logs_tempo_accept"}

        events = data.get("events") or []
        if not events:
            return {"ok": False, "error": "no tempo events found", "upcoming": [], "source": "engine_logs_tempo_accept"}
        if not cur_norm:
            return {
                "ok": True,
                "source": "engine_logs_tempo_accept_waiting_for_current",
                "current_title_found": False,
                "current_title": current_title,
                "upcoming": [],
                "entries_considered": 0,
                "barrier_hit": False,
            }

        anchor_idx, _ = self._anchor_index_for_current(events, cur_norm)
        if anchor_idx is None:
            return {
                "ok": True,
                "source": "engine_logs_tempo_accept_unanchored",
                "current_title_found": False,
                "current_title": current_title,
                "upcoming": [],
                "entries_considered": 0,
                "barrier_hit": False,
            }

        seen: set[str] = set()
        out: List[Dict[str, Any]] = []
        entries_considered = 0
        barrier_hit = False

        for ev in events[anchor_idx:]:
            if not isinstance(ev, TempoEvent):
                continue
            if ev.kind == "fail_open":
                barrier_hit = True
                break
            if ev.kind != "accept":
                continue

            entries_considered += 1
            if ev.a_norm != cur_norm and not out:
                continue

            b_norm = ev.b_norm.strip()
            if not b_norm or b_norm == cur_norm or b_norm in seen:
                cur_norm = b_norm or cur_norm
                continue

            seen.add(b_norm)
            out.append(
                {
                    "title": ev.b_title,
                    "title_display": self.display_title(str(ev.b_title or "")),
                    "playlist": None,
                    "ts": ev.ts_raw,
                    "from_title": ev.a_title,
                    "delta_pct": ev.delta_pct,
                    "max_delta_pct": ev.max_delta_pct,
                    "attempt": ev.attempt,
                }
            )
            cur_norm = b_norm
            if len(out) >= n:
                break

        return {
            "ok": True,
            "source": "engine_logs_tempo_accept_after_current",
            "current_title_found": True,
            "current_title": current_title,
            "upcoming": out,
            "entries_considered": entries_considered,
            "barrier_hit": barrier_hit,
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
        s = s.replace("_-_", " - ").replace("_", " ")
        s = re.sub(r"\s+", " ", s).strip()
        return s or None

    def extract_preprocess_titles(self, engine_container: str, tail: int = 2500) -> Dict[str, Any]:
        txt, lines = self._iter_clean_log_lines(engine_container, tail)
        err = self._ok_or_error(txt, "engine_logs", "engine_container", engine_container)
        if err:
            return {**err, "titles": []}

        titles: List[str] = []
        for line in lines:
            m = self._RE_PREPROCESS.search(line)
            if m:
                t = self._clean_preprocess_title((m.group("rest") or "").strip())
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
        cur_norm = self.normalize_title(current_title or "")

        tempo_data = self.extract_tempo_selected_titles(engine_container, tail=tail)
        if tempo_data.get("ok"):
            tempo_titles = [t for t in (tempo_data.get("titles") or []) if isinstance(t, str) and t.strip()]
            if tempo_titles:
                items = [
                    {"title": t, "title_display": self.display_title(t), "title_norm": self.normalize_title(t), "playlist": None, "ts": None}
                    for t in tempo_titles
                ]
                out = self._slice_from_current(
                    items=items,
                    current_norm=cur_norm,
                    norm_key="title_norm",
                    n=n,
                    fallback_mult=4,
                    source_after="engine_logs_tempo_after_current",
                    source_fallback="engine_logs_tempo_fallback_tail",
                    current_title=current_title,
                )
                out["upcoming"] = [e["title_display"] for e in out["upcoming"]]
                return out

        data = self.extract_preprocess_titles(engine_container, tail=tail)
        if not data.get("ok"):
            return {"ok": False, "error": data.get("error"), "upcoming": [], "source": "engine_logs"}

        titles = [t for t in (data.get("titles") or []) if isinstance(t, str) and t.strip()]
        if not titles:
            return {"ok": False, "error": "no preprocess titles found", "upcoming": [], "source": "engine_logs"}

        items = [
            {"title": t, "title_display": self.display_title(t), "title_norm": self.normalize_title(t), "playlist": None, "ts": None}
            for t in self._dedupe_keep_order(titles)
        ]
        out = self._slice_from_current(
            items=items,
            current_norm=cur_norm,
            norm_key="title_norm",
            n=n,
            fallback_mult=4,
            source_after="engine_logs_preprocess_after_current",
            source_fallback="engine_logs_preprocess_fallback_tail",
            current_title=current_title,
        )
        out["upcoming"] = [e["title_display"] for e in out["upcoming"]]
        return out

    # ----------------------- Scheduler NEXT -----------------------

    def extract_scheduler_next_entries(self, scheduler_container: str, tail: int = 2500) -> Dict[str, Any]:
        txt, lines = self._iter_clean_log_lines(scheduler_container, tail)
        err = self._ok_or_error(txt, "scheduler_logs", "scheduler_container", scheduler_container)
        if err:
            return {**err, "entries": []}

        entries: List[NextEntry] = []
        for line in lines:
            m = self._RE_SCHED_NEXT.search(line)
            if not m:
                continue
            ts_raw = m.group("ts") or ""
            title_raw = m.group("title") or ""
            entries.append(
                NextEntry(
                    ts_raw=ts_raw,
                    ts=self._parse_sched_ts(ts_raw),
                    title_raw=title_raw,
                    title_norm=self.normalize_title(title_raw),
                    playlist=m.group("playlist") or "",
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

        match = next((e for e in reversed(entries) if (e.get("title_norm") or "") == cur_norm), None)
        if not match:
            return {"ok": True, "playlist": None, "match": None, "current_title": current_title, "current_norm": cur_norm}

        return {"ok": True, "playlist": match.get("playlist"), "match": match, "current_title": current_title, "current_norm": cur_norm}

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

        items = [
            {
                "title": e.get("title"),
                "title_display": e.get("title_display") or self.display_title(str(e.get("title") or "")),
                "title_norm": e.get("title_norm"),
                "playlist": e.get("playlist"),
                "ts": e.get("ts"),
            }
            for e in raw_entries
        ]
        return self._slice_from_current(
            items=items,
            current_norm=cur_norm,
            norm_key="title_norm",
            n=n,
            fallback_mult=8,
            source_after="scheduler_logs_after_current",
            source_fallback="scheduler_logs_fallback_tail",
            current_title=current_title,
        )

    # ----------------------- Engine STREAM_START -----------------------

    def last_engine_stream_start(self, engine_container: str, tail: int = 800, recent_window_s: int = 10) -> Dict[str, Any]:
        txt, lines = self._iter_clean_log_lines(engine_container, tail)
        err = self._ok_or_error(txt, "engine_logs", "engine_container", engine_container)
        if err:
            return {**err, "line": None, "recent": False}

        last_line = None
        last_ts = None

        for line in lines:
            if not self._RE_STREAM_START.search(line):
                continue
            last_line = line.strip()
            ts_raw = self._extract_log_ts_raw(last_line)
            last_ts = self._parse_sched_ts(ts_raw) if ts_raw else None

        if not last_line:
            return {"ok": True, "source": "engine_logs", "engine_container": engine_container, "line": None, "recent": False}

        recent = False
        age_s = None
        if last_ts:
            try:
                age_s = int((dt.datetime.now() - last_ts).total_seconds())
                recent = 0 <= age_s <= int(recent_window_s)
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
