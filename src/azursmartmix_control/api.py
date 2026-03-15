from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

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


_NOCACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


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
    environment: Dict[str, str] = Field(default_factory=dict)
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

    def _json_nocache(data: Dict[str, Any]) -> JSONResponse:
        return JSONResponse(data, headers=_NOCACHE_HEADERS)

    def _text_nocache(text: str) -> PlainTextResponse:
        return PlainTextResponse(text, headers=_NOCACHE_HEADERS)

    def _panel_resources_payload() -> Dict[str, Any]:
        raw = docker_client.host_resources_summary()
        return {
            "ok": bool(raw.get("ok")),
            "now_utc": raw.get("now_utc"),
            "source": raw.get("source"),
            "cpu": raw.get("cpu") or {},
            "memory": raw.get("memory") or {},
            "loadavg": raw.get("loadavg") or {},
        }

    def _panel_runtime_payload() -> Dict[str, Any]:
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

    async def _resolve_now_and_upcoming(upcoming_n: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        ic = await ice.now_playing()
        icecast_title = None
        if isinstance(ic, dict) and ic.get("ok"):
            icecast_title = _display_title_or_none(ic.get("title") or (ic.get("raw") or {}).get("title"))

        tempo_runtime = docker_client.extract_tempo_runtime_state(
            engine_container=settings.engine_container,
            tail=2500,
        )
        runtime_title = None
        if isinstance(tempo_runtime, dict) and tempo_runtime.get("ok"):
            runtime_title = _display_title_or_none(tempo_runtime.get("current_title"))

        current_title = icecast_title or runtime_title
        now_source = "icecast_metadata" if icecast_title else ("engine_tempo_runtime" if runtime_title else None)

        upcoming_tempo = docker_client.compute_upcoming_from_tempo_accepts(
            engine_container=settings.engine_container,
            current_title=current_title,
            n=max(12, upcoming_n + 2),
            tail=3000,
        )
        tempo_items = upcoming_tempo.get("upcoming") if isinstance(upcoming_tempo, dict) else None
        if not isinstance(tempo_items, list):
            tempo_items = []

        upcoming_sched = docker_client.compute_upcoming_from_scheduler_next(
            scheduler_container=settings.scheduler_container,
            current_title=current_title,
            n=max(12, upcoming_n + 2),
            tail=3000,
        )
        sched_items = upcoming_sched.get("upcoming") if isinstance(upcoming_sched, dict) else None
        if not isinstance(sched_items, list):
            sched_items = []

        pl_observed = docker_client.infer_playlist_for_title_from_scheduler(
            scheduler_container=settings.scheduler_container,
            current_title=current_title,
            tail=3000,
        )
        playlist_effective = pl_observed.get("playlist") if isinstance(pl_observed, dict) else None

        predicted_next = None
        if tempo_items:
            predicted_next = tempo_items[0]
        elif sched_items:
            predicted_next = sched_items[0]

        ss = docker_client.last_engine_stream_start(
            engine_container=settings.engine_container,
            tail=1000,
            recent_window_s=12,
        )

        using_tempo = bool(tempo_items)
        chosen = (tempo_items if using_tempo else sched_items)[:upcoming_n]

        now_payload = {
            "ok": bool(current_title),
            "mount": settings.icecast_mount,
            "source": "icecast(metadata)+engine_tempo(select)+scheduler(NEXT)+engine(STREAM_START)",
            "now_source": now_source,
            "title_effective": current_title,
            "playlist_effective": playlist_effective,
            "title_observed": icecast_title,
            "title_runtime": runtime_title,
            "playlist_observed": playlist_effective,
            "scheduler_match_observed": pl_observed.get("match") if isinstance(pl_observed, dict) else None,
            "engine_stream_start": ss,
            "tempo_runtime": tempo_runtime,
            "predicted_next": predicted_next,
            "debug": {
                "upcoming_primary_source": upcoming_tempo.get("source") if isinstance(upcoming_tempo, dict) else None,
                "upcoming_secondary_source": upcoming_sched.get("source") if isinstance(upcoming_sched, dict) else None,
                "tempo_upcoming_count": len(tempo_items),
                "scheduler_upcoming_count": len(sched_items),
            },
        }

        upcoming_payload = {
            "ok": True,
            "current_title_observed": current_title,
            "source": {
                "primary": (
                    upcoming_tempo.get("source")
                    if using_tempo and isinstance(upcoming_tempo, dict)
                    else (upcoming_sched.get("source") if isinstance(upcoming_sched, dict) else None)
                ),
                "secondary": upcoming_sched.get("source") if using_tempo and isinstance(upcoming_sched, dict) else None,
            },
            "upcoming": chosen,
            "debug": {
                "title_source": now_source,
                "tempo_runtime": tempo_runtime,
                "tempo_accept": upcoming_tempo,
                "scheduler": upcoming_sched,
                "used_source": "tempo_accept" if using_tempo else "scheduler",
            },
        }

        return now_payload, upcoming_payload

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"ok": True}

    @app.get("/status")
    def status() -> Dict[str, Any]:
        return docker_client.runtime_summary(settings.engine_container, settings.scheduler_container)

    @app.get("/logs")
    def logs(
        service: str = Query(..., description="engine|scheduler|<container_name>"),
        tail: int = Query(0, description="lines to tail (0 = default)"),
    ) -> PlainTextResponse:
        tail_eff = tail if tail > 0 else settings.log_tail_lines_default
        tail_eff = max(1, min(tail_eff, settings.log_tail_lines_max))

        if service == "engine":
            name = settings.engine_container
        elif service == "scheduler":
            name = settings.scheduler_container
        else:
            name = service

        return _text_nocache(docker_client.tail_logs(name=name, tail=tail_eff))

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

    @app.get("/compose/engine_env")
    def compose_engine_env() -> Dict[str, Any]:
        data = get_env_from_host_envfile(settings.azuramix_env_file)
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

    @app.get("/scheduler/upcoming")
    async def scheduler_upcoming(n: int = Query(10, ge=1, le=50)) -> JSONResponse:
        data = await sched.upcoming(n=n)
        return JSONResponse(data, headers=_NOCACHE_HEADERS)

    @app.get("/panel/engine_env")
    def panel_engine_env() -> Dict[str, Any]:
        return get_service_env(settings.compose_path, settings.compose_service_engine)

    @app.get("/panel/resources")
    def panel_resources() -> JSONResponse:
        return _json_nocache(_panel_resources_payload())

    @app.get("/panel/runtime")
    def panel_runtime() -> JSONResponse:
        return _json_nocache(_panel_runtime_payload())

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
    async def panel_now() -> JSONResponse:
        now_payload, _ = await _resolve_now_and_upcoming(upcoming_n=10)
        return _json_nocache(now_payload)

    @app.get("/panel/upcoming")
    async def panel_upcoming(n: int = Query(10, ge=1, le=30)) -> JSONResponse:
        _, upcoming_payload = await _resolve_now_and_upcoming(upcoming_n=n)
        return _json_nocache(upcoming_payload)

    @app.get("/panel/dashboard")
    async def panel_dashboard(
        upcoming_n: int = Query(10, ge=1, le=30),
        include_logs: bool = Query(False),
        engine_log_tail: int = Query(200, ge=1, le=2000),
        scheduler_log_tail: int = Query(200, ge=1, le=2000),
    ) -> JSONResponse:
        now_payload, upcoming_payload = await _resolve_now_and_upcoming(upcoming_n=upcoming_n)

        payload: Dict[str, Any] = {
            "ok": True,
            "resources": _panel_resources_payload(),
            "runtime": _panel_runtime_payload(),
            "now": now_payload,
            "upcoming": upcoming_payload,
        }

        if include_logs:
            payload["logs"] = {
                "engine": docker_client.tail_logs(name=settings.engine_container, tail=engine_log_tail),
                "scheduler": docker_client.tail_logs(name=settings.scheduler_container, tail=scheduler_log_tail),
            }

        return _json_nocache(payload)

    return app
