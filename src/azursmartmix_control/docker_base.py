from __future__ import annotations

import datetime as dt
import os
import re
import shlex
import subprocess
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import docker
from docker.errors import DockerException, NotFound


class DockerBase:
    """Socle runtime Docker + helpers communs de parsing/normalisation."""

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
        m = DockerBase._RE_LOG_TS.search(line or "")
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
        m = DockerBase._RE_ATTEMPT.search(line or "")
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
        return DockerBase._RE_DOCKER_TS_PREFIX.sub("", line, count=1).strip()

    @staticmethod
    def _coerce_rel_title(rel: str) -> Optional[str]:
        s = (rel or "").strip()
        if not s:
            return None
        s = os.path.basename(s)
        s = DockerBase._RE_EXT.sub("", s).strip()
        s = s.replace("_-_", " - ")
        s = s.replace("_", " ")
        s = re.sub(r"\s+", " ", s).strip()
        return s or None

    @staticmethod
    def display_title(s: str) -> str:
        return DockerBase._coerce_rel_title(s) or ""

    @staticmethod
    def normalize_title(s: str) -> str:
        t = DockerBase.display_title(s).lower().strip()
        t = re.sub(r"\[[^\]]*\]", "", t)
        t = re.sub(r"\([^)]*\)", "", t)
        t = re.sub(r"[^a-z0-9]+", "", t)
        return t

    @staticmethod
    def _dedupe_keep_order(items: List[str]) -> List[str]:
        out: List[str] = []
        seen: set[str] = set()
        for x in items:
            n = DockerBase.normalize_title(x)
            if not n or n in seen:
                continue
            seen.add(n)
            out.append(DockerBase.display_title(x))
        return out

    def _iter_clean_log_lines(self, name: str, tail: int) -> Tuple[str, List[str]]:
        txt = self.tail_logs(name, tail=tail)
        return txt, [self._strip_docker_prefix(x) for x in txt.splitlines()] if txt else []

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
        else:
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
                    data[k] = int(v.strip().split()[0]) * 1024
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
            "cpu": {
                "percent": self._sample_host_cpu_percent(),
                "sample": "proc/stat",
            },
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
        return DockerBase._coerce_rel_title(path)

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

    # ----------------------- Compat preprocess -----------------------

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
