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
        upcoming_engine: Dict[str, Any],
        upcoming_sched: Dict[str, Any],
        limit: int,
    ) -> List[Dict[str, Any]]:
        if not isinstance(upcoming_engine, dict) or not upcoming_engine.get("ok"):
            return []

        engine_items = upcoming_engine.get("upcoming") or []
        if not isinstance(engine_items, list) or not engine_items:
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
        for raw_item in engine_items:
            if not isinstance(raw_item, dict):
                continue
            title = str(raw_item.get("title") or raw_item.get("title_display") or "").strip()
            norm = docker_client.normalize_title(title)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            sched_entry = sched_map.get(norm) or {}
            out.append(
                {
                    "title": sched_entry.get("title") or raw_item.get("title") or title,
                    "title_display": raw_item.get("title_display") or sched_entry.get("title_display") or docker_client.display_title(title),
                    "playlist": sched_entry.get("playlist"),
                    "ts": sched_entry.get("ts"),
                    "bpm": raw_item.get("bpm"),
                    "decision": raw_item.get("decision"),
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
        title_observed = None
        if isinstance(ic, dict) and ic.get("ok"):
            title_observed = ic.get("title") or (ic.get("raw") or {}).get("title")

        upcoming_sched = docker_client.compute_upcoming_from_scheduler_next(
            scheduler_container=settings.scheduler_container,
            current_title=title_observed,
            n=12,
            tail=3000,
        )

        ss = docker_client.last_engine_stream_start(
            engine_container=settings.engine_container,
            tail=1000,
            recent_window_s=12,
        )

        bpm_observed = docker_client.infer_bpm_for_title_from_engine(
            engine_container=settings.engine_container,
            title=title_observed,
            tail=2500,
        )

        pl_observed = docker_client.infer_playlist_for_title_from_scheduler(
            scheduler_container=settings.scheduler_container,
            current_title=title_observed,
            tail=3000,
        )
        playlist_observed = pl_observed.get("playlist") if isinstance(pl_observed, dict) else None

        eff = _compute_effective_now_and_upcoming(title_observed, upcoming_sched)
        effective_now = eff.get("effective_now")

        now_mode = "observed"
        title_effective = title_observed
        playlist_effective = playlist_observed

        predicted_next = None
        if effective_now and isinstance(effective_now, dict):
            title_effective = effective_now.get("title_display") or docker_client.display_title(
                str(effective_now.get("title") or "")
            )
            playlist_effective = effective_now.get("playlist") or playlist_effective
            now_mode = "promoted_from_upcoming"

            effective_upcoming = eff.get("effective_upcoming") or []
            if isinstance(effective_upcoming, list) and effective_upcoming:
                predicted_next = effective_upcoming[0]
        else:
            raw_up = eff.get("raw_upcoming") or []
            if isinstance(raw_up, list) and raw_up:
                predicted_next = raw_up[0]

        bpm_effective = bpm_observed.get("bpm") if isinstance(bpm_observed, dict) else None

        return {
            "ok": bool(title_effective),
            "mount": settings.icecast_mount,
            "source": "icecast(observed)+scheduler(NEXT)+engine(hint)",
            "now_mode": now_mode,
            "title_effective": title_effective,
            "playlist_effective": playlist_effective,
            "title_observed": title_observed,
            "playlist_observed": playlist_observed,
            "bpm_effective": bpm_effective,
            "bpm_observed": bpm_observed.get("bpm") if isinstance(bpm_observed, dict) else None,
            "scheduler_match_observed": pl_observed.get("match") if isinstance(pl_observed, dict) else None,
            "engine_stream_start": ss,
            "predicted_next": predicted_next,
            "debug": {
                "observed_norm": eff.get("observed_norm"),
                "upcoming_primary_source": upcoming_sched.get("source") if isinstance(upcoming_sched, dict) else None,
                "upcoming_count_raw": len(eff.get("raw_upcoming") or []),
                "promoted": bool(effective_now),
            },
        }

    @app.get("/panel/upcoming")
    async def panel_upcoming(n: int = Query(10, ge=1, le=30)) -> Dict[str, Any]:
        ic = await ice.now_playing()
        current_title = None
        if isinstance(ic, dict) and ic.get("ok"):
            current_title = ic.get("title")

        upcoming_sched = docker_client.compute_upcoming_from_scheduler_next(
            scheduler_container=settings.scheduler_container,
            current_title=current_title,
            n=max(12, n + 2),
            tail=3000,
        )

        eff = _compute_effective_now_and_upcoming(current_title, upcoming_sched)
        effective_upcoming = eff.get("effective_upcoming") or []
        if not isinstance(effective_upcoming, list):
            effective_upcoming = []
        effective_upcoming = effective_upcoming[:n]

        upcoming_engine = docker_client.compute_upcoming_from_preprocess(
            engine_container=settings.engine_container,
            current_title=current_title,
            n=n,
            tail=2500,
        )

        engine_upcoming = _engine_titles_to_upcoming_entries(upcoming_engine, upcoming_sched, n)
        using_engine = bool(engine_upcoming)
        upcoming_titles: List[str] = [str(x.get("title_display") or x.get("title") or "") for x in engine_upcoming if isinstance(x, dict)]

        return {
            "ok": True,
            "current_title_observed": current_title,
            "source": {
                "primary": upcoming_engine.get("source") if using_engine and isinstance(upcoming_engine, dict) else (upcoming_sched.get("source") if isinstance(upcoming_sched, dict) else None),
                "secondary": upcoming_sched.get("source") if using_engine and isinstance(upcoming_sched, dict) else (upcoming_engine.get("source") if isinstance(upcoming_engine, dict) else None),
            },
            "upcoming": (engine_upcoming if using_engine else effective_upcoming)[:n],
            "upcoming_titles": upcoming_titles[:n],
            "debug": {
                "observed_norm": eff.get("observed_norm"),
                "promoted_now": eff.get("effective_now"),
                "raw_upcoming_head": (eff.get("raw_upcoming") or [])[:3],
                "scheduler": upcoming_sched,
                "engine_preprocess": upcoming_engine,
                "engine_upcoming": engine_upcoming[:n],
                "used_source": "engine" if using_engine else "scheduler",
            },
        }

    return app
