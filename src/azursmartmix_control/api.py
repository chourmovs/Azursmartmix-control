from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from azursmartmix_control.config import Settings
from azursmartmix_control.docker_client import DockerClient
from azursmartmix_control.scheduler_client import SchedulerClient
from azursmartmix_control.compose_reader import (
    get_service_env,
    get_env_from_host_envfile,
    set_env_in_host_envfile,
)
from azursmartmix_control.icecast_client import IcecastClient
from azursmartmix_control.runtime_queue_state import get_state


def _fmt_duration(seconds: Optional[int]) -> Optional[str]:
    if seconds is None:
        return None
    s = int(seconds)
    if s < 0:
        s = 0
    d, rem = divmod(s, 86400)
    h, rem = divmod(rem, 3600)
    m, sec = divmod(rem, 60)
    if d > 0:
        return f"{d}d {h:02d}:{m:02d}:{sec:02d}"
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _fmt_cmd_result(r: Dict[str, Any]) -> str:
    if not isinstance(r, dict):
        return str(r)

    def line(k: str, v: Any) -> str:
        vv = "" if v is None else str(v)
        return f"{k}: {vv}"

    out = []
    out.append(line("ok", r.get("ok")))
    out.append(line("rc", r.get("rc")))
    out.append(line("cwd", r.get("cwd")))
    out.append(line("cmd", r.get("cmd")))
    if r.get("started_utc"):
        out.append(line("started_utc", r.get("started_utc")))
    if r.get("ended_utc"):
        out.append(line("ended_utc", r.get("ended_utc")))
    if r.get("duration_ms") is not None:
        out.append(line("duration_ms", r.get("duration_ms")))

    stdout = (r.get("stdout") or "").strip()
    stderr = (r.get("stderr") or "").strip()

    if stdout:
        out.append("")
        out.append("---- stdout ----")
        out.append(stdout)

    if stderr:
        out.append("")
        out.append("---- stderr ----")
        out.append(stderr)

    return "\n".join(out).strip() + "\n"


_RE_SAFE_TAG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _build_image_ref(settings: Settings, tag: Optional[str]) -> str:
    if tag:
        t = tag.strip()
        if not _RE_SAFE_TAG.match(t):
            raise ValueError(f"invalid tag: {tag!r}")
        repo = (settings.azursmartmix_repo or "").strip() or "chourmovs/azursmartmix"
        return f"{repo}:{t}"
    return (settings.azursmartmix_image or "chourmovs/azursmartmix:latest").strip()


class ComposeEnvSaveRequest(BaseModel):
    # UI envoie un dict KEY->VALUE
    environment: Dict[str, str] = Field(default_factory=dict)

    # legacy field (compose env could be dict/list). Kept for compatibility with existing UI payloads.
    env_format_prefer: str = Field(default="dict", description="dict|list (legacy, ignored for env_file)")


def _display_title_or_none(value: Any) -> Optional[str]:
    s = str(value or "").strip()
    if not s:
        return None
    s = DockerClient.display_title(s)
    return s or None


def create_api(settings: Settings) -> FastAPI:
    app = FastAPI(title="AzurSmartMix Control API", version="0.1.0")

    docker_client = DockerClient()

    now_ep = os.getenv("SCHED_NOW_ENDPOINT", "").strip() or None
    sched = SchedulerClient(settings.sched_base_url, now_endpoint=now_ep)

    ice = IcecastClient(
        scheme=settings.icecast_scheme,
        host=settings.icecast_host,
        port=settings.icecast_port,
        status_path=settings.icecast_status_path,
        mount=settings.icecast_mount,
    )

    def _strict_icecast_title(ic_payload: Dict[str, Any]) -> Optional[str]:
        if not isinstance(ic_payload, dict) or not ic_payload.get("ok"):
            return None
        return _display_title_or_none(
            ic_payload.get("title") or (ic_payload.get("raw") or {}).get("title")
        )

    def _strict_tempo_upcoming(current_title: Optional[str], n: int) -> Dict[str, Any]:
        if not current_title:
            return {
                "ok": True,
                "source": "engine_logs_tempo_accept_waiting_for_icecast",
                "current_title_found": False,
                "current_title": None,
                "upcoming": [],
                "entries_considered": 0,
            }

        data = docker_client.compute_upcoming_from_tempo_accepts(
            engine_container=settings.engine_container,
            current_title=current_title,
            n=max(12, n + 2),
            tail=3000,
        )
        if not isinstance(data, dict):
            return {
                "ok": False,
                "source": "engine_logs_tempo_accept",
                "current_title_found": False,
                "current_title": current_title,
                "upcoming": [],
                "error": "invalid helper payload",
            }

        if not bool(data.get("current_title_found")):
            return {
                "ok": True,
                "source": "engine_logs_tempo_accept_unanchored",
                "current_title_found": False,
                "current_title": current_title,
                "upcoming": [],
                "entries_considered": int(data.get("entries_considered") or 0),
            }

        items = data.get("upcoming") or []
        if not isinstance(items, list):
            items = []

        out: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            out.append(item)
            if len(out) >= n:
                break

        return {
            "ok": True,
            "source": "engine_logs_tempo_accept_after_current",
            "current_title_found": True,
            "current_title": current_title,
            "upcoming": out,
            "entries_considered": int(data.get("entries_considered") or 0),
        }


    @app.get("/runtime/queue")
    def runtime_queue():
        return get_state()
    
    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"ok": True}

    @app.get("/status")
    def status() -> Dict[str, Any]:
        return docker_client.runtime_summary(settings.engine_container, settings.scheduler_container)

    @app.get("/logs", response_class=PlainTextResponse)
    def logs(
        service: str = Query(..., description="engine|scheduler|<container_name>"),
        tail: int = Query(0, description="lines to tail (0 = default)"),
    ) -> str:
        tail_eff = tail if tail > 0 else settings.log_tail_lines_default
        tail_eff = max(1, min(tail_eff, settings.log_tail_lines_max))

        if service == "engine":
            name = settings.engine_container
        elif service == "scheduler":
            name = settings.scheduler_container
        else:
            name = service

        return docker_client.tail_logs(name=name, tail=tail_eff)

    # ------------------- Compose control endpoints -------------------

    @app.post("/ops/compose/down", response_class=PlainTextResponse)
    def ops_compose_down() -> str:
        r = docker_client.compose_down(settings.azuramix_dir)
        return _fmt_cmd_result(r)

    @app.post("/ops/compose/up", response_class=PlainTextResponse)
    def ops_compose_up() -> str:
        r = docker_client.compose_up(settings.azuramix_dir)
        return _fmt_cmd_result(r)

    @app.post("/ops/compose/recreate", response_class=PlainTextResponse)
    def ops_compose_recreate() -> str:
        r = docker_client.compose_recreate(settings.azuramix_dir)
        return _fmt_cmd_result(r)

    @app.post("/ops/compose/update", response_class=PlainTextResponse)
    def ops_compose_update(tag: Optional[str] = Query(default=None, description="image tag e.g. latest, beta1")) -> str:
        try:
            image_ref = _build_image_ref(settings, tag)
        except Exception as e:
            return f"ok: False\nerror: {e}\n"

        r = docker_client.compose_update(settings.azuramix_dir, image_ref)

        if not isinstance(r, dict) or "step_down" not in r:
            return _fmt_cmd_result(r)

        lines: List[str] = []
        lines.append("== step: docker compose down ==")
        lines.append(_fmt_cmd_result(r.get("step_down") or {}))
        lines.append("")
        lines.append(f"== step: docker image rm -f {image_ref} || true ==")
        lines.append(_fmt_cmd_result(r.get("step_image_rm") or {}))
        lines.append("")
        lines.append(f"image_ref: {image_ref}")
        lines.append(f"overall_ok: {bool(r.get('ok'))}")
        return "\n".join(lines).strip() + "\n"

    # ------------------- Settings editor (env_file on host) -------------------
    # API contract remains the same: /compose/engine_env
    # Implementation: read/write /var/azuramix/azuramix.env only.

    @app.get("/compose/engine_env")
    def compose_engine_env() -> Dict[str, Any]:
        data = get_env_from_host_envfile(settings.azuramix_env_file)
        # keep UI stable: pretend this is "engine env"
        data["service"] = settings.compose_service_engine
        data["restart_required"] = False
        return data

    @app.post("/compose/engine_env")
    def compose_engine_env_save(req: ComposeEnvSaveRequest) -> Dict[str, Any]:
        r = set_env_in_host_envfile(
            env_file_path=settings.azuramix_env_file,
            env_updates=req.environment or {},
        )
        r["service"] = settings.compose_service_engine
        r["restart_required"] = True
        r["message"] = "Saved to azuramix.env. Need to restart (docker compose up -d) to take effect."
        return r

    # ------------------- Existing endpoints -------------------

    @app.get("/scheduler/upcoming")
    async def scheduler_upcoming(n: int = Query(10, ge=1, le=50)) -> JSONResponse:
        data = await sched.upcoming(n=n)
        return JSONResponse(data)

    @app.get("/panel/engine_env")
    def panel_engine_env() -> Dict[str, Any]:
        # legacy: read-only view from mounted compose file inside container
        return get_service_env(settings.compose_path, settings.compose_service_engine)

    @app.get("/panel/resources")
    def panel_resources() -> Dict[str, Any]:
        raw = docker_client.host_resources_summary()
        return {
            "ok": bool(raw.get("ok")),
            "now_utc": raw.get("now_utc"),
            "source": raw.get("source"),
            "cpu": raw.get("cpu") or {},
            "memory": raw.get("memory") or {},
            "loadavg": raw.get("loadavg") or {},
        }

    @app.get("/panel/runtime")
    def panel_runtime() -> Dict[str, Any]:
        raw = docker_client.runtime_summary(settings.engine_container, settings.scheduler_container)

        eng = raw.get("engine") or {}
        sch = raw.get("scheduler") or {}

        def pack(x: Dict[str, Any]) -> Dict[str, Any]:
            if not x.get("present"):
                return {"present": False, "name": x.get("name"), "status": "missing"}
            return {
                "present": True,
                "name": x.get("name"),
                "image": x.get("image"),
                "status": x.get("status"),
                "health": x.get("health"),
                "uptime": _fmt_duration(x.get("uptime_s")),
                "age": _fmt_duration(x.get("age_s")),
            }

        return {
            "now_utc": raw.get("now_utc"),
            "docker_ping": raw.get("docker_ping"),
            "engine": pack(eng),
            "scheduler": pack(sch),
        }

    # --- (tout le reste de ton API existante inchangée) ---

    def _engine_titles_to_upcoming_entries(
        titles: List[str],
        upcoming_sched: Dict[str, Any],
        limit: int,
    ) -> List[Dict[str, Any]]:
        if not isinstance(titles, list) or not titles:
            return []

        sched_map: Dict[str, Dict[str, Any]] = {}
        if isinstance(upcoming_sched, dict) and upcoming_sched.get("ok"):
            raw_sched = upcoming_sched.get("upcoming") or []
            if isinstance(raw_sched, list):
                for entry in raw_sched:
                    if not isinstance(entry, dict):
                        continue
                    norm = docker_client.normalize_title(str(entry.get("title") or ""))
                    if norm and norm not in sched_map:
                        sched_map[norm] = entry

        out: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for raw_title in titles:
            title = str(raw_title or "").strip()
            norm = docker_client.normalize_title(title)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            sched_entry = sched_map.get(norm) or {}
            out.append(
                {
                    "title": sched_entry.get("title") or title,
                    "title_display": sched_entry.get("title_display") or docker_client.display_title(title),
                    "playlist": sched_entry.get("playlist"),
                    "ts": sched_entry.get("ts"),
                }
            )
            if len(out) >= limit:
                break

        return out

    def _compute_effective_now_and_upcoming(
        title_observed: Optional[str],
        upcoming_sched: Dict[str, Any],
    ) -> Dict[str, Any]:
        observed_norm = docker_client.normalize_title(title_observed or "")
        upcoming_list = []
        if isinstance(upcoming_sched, dict) and upcoming_sched.get("ok"):
            u = upcoming_sched.get("upcoming") or []
            if isinstance(u, list):
                upcoming_list = [x for x in u if isinstance(x, dict)]

        effective_now = None
        effective_upcoming = upcoming_list

        if upcoming_list:
            first = upcoming_list[0]
            first_title_raw = str(first.get("title") or "")
            first_norm = docker_client.normalize_title(first_title_raw)

            if (not observed_norm) or (first_norm and first_norm != observed_norm):
                effective_now = first
                effective_upcoming = upcoming_list[1:]

        return {
            "observed_norm": observed_norm,
            "effective_now": effective_now,
            "effective_upcoming": effective_upcoming,
            "raw_upcoming": upcoming_list,
        }

    @app.get("/panel/now")
    async def panel_now() -> Dict[str, Any]:
        ic = await ice.now_playing()
        icecast_title = _strict_icecast_title(ic)

        tempo_runtime = docker_client.extract_tempo_runtime_state(
            engine_container=settings.engine_container,
            tail=2500,
        )

        title_effective = icecast_title
        now_source = "icecast_metadata" if icecast_title else None

        upcoming_tempo = _strict_tempo_upcoming(current_title=title_effective, n=6)

        pl_observed = docker_client.infer_playlist_for_title_from_scheduler(
            scheduler_container=settings.scheduler_container,
            current_title=title_effective,
            tail=3000,
        ) if title_effective else {"ok": True, "playlist": None, "match": None}
        playlist_effective = pl_observed.get("playlist") if isinstance(pl_observed, dict) else None

        predicted_next = None
        tempo_items = upcoming_tempo.get("upcoming") if isinstance(upcoming_tempo, dict) else None
        if isinstance(tempo_items, list) and tempo_items:
            predicted_next = tempo_items[0]

        ss = docker_client.last_engine_stream_start(
            engine_container=settings.engine_container,
            tail=1000,
            recent_window_s=12,
        )

        return {
            "ok": bool(title_effective),
            "mount": settings.icecast_mount,
            "source": "icecast(metadata_only)+engine_tempo(select_ok_after_current)+engine(STREAM_START)",
            "now_source": now_source,
            "title_effective": title_effective,
            "playlist_effective": playlist_effective,
            "title_observed": icecast_title,
            "title_runtime": None,
            "playlist_observed": playlist_effective,
            "scheduler_match_observed": pl_observed.get("match") if isinstance(pl_observed, dict) else None,
            "engine_stream_start": ss,
            "tempo_runtime": tempo_runtime,
            "predicted_next": predicted_next,
            "debug": {
                "icecast_ok": bool(isinstance(ic, dict) and ic.get("ok")),
                "icecast_error": (ic.get("error") if isinstance(ic, dict) else None),
                "upcoming_primary_source": upcoming_tempo.get("source") if isinstance(upcoming_tempo, dict) else None,
                "tempo_upcoming_count": len(tempo_items or []) if isinstance(tempo_items, list) else 0,
                "tempo_current_title_found": bool(upcoming_tempo.get("current_title_found")) if isinstance(upcoming_tempo, dict) else False,
            },
        }

    @app.get("/panel/upcoming")
    async def panel_upcoming(n: int = Query(10, ge=1, le=30)) -> Dict[str, Any]:
        ic = await ice.now_playing()
        icecast_title = _strict_icecast_title(ic)

        tempo_runtime = docker_client.extract_tempo_runtime_state(
            engine_container=settings.engine_container,
            tail=2500,
        )

        current_title = icecast_title
        upcoming_tempo = _strict_tempo_upcoming(current_title=current_title, n=n)

        chosen = upcoming_tempo.get("upcoming") if isinstance(upcoming_tempo, dict) else []
        if not isinstance(chosen, list):
            chosen = []

        return {
            "ok": True,
            "current_title_observed": current_title,
            "source": {
                "primary": upcoming_tempo.get("source") if isinstance(upcoming_tempo, dict) else None,
                "secondary": None,
            },
            "upcoming": chosen[:n],
            "debug": {
                "title_source": "icecast_metadata" if icecast_title else None,
                "icecast_ok": bool(isinstance(ic, dict) and ic.get("ok")),
                "icecast_error": (ic.get("error") if isinstance(ic, dict) else None),
                "tempo_runtime": tempo_runtime,
                "tempo_accept": upcoming_tempo,
                "used_source": "tempo_accept_strict",
            },
        }

    return app
