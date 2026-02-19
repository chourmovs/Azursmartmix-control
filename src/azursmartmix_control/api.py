from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from azursmartmix_control.config import Settings
from azursmartmix_control.docker_client import DockerClient
from azursmartmix_control.scheduler_client import SchedulerClient
from azursmartmix_control.compose_reader import get_service_env
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

    # --- raw status (still useful for debug) ---
    @app.get("/status")
    def status() -> Dict[str, Any]:
        return docker_client.runtime_summary(settings.engine_container, settings.scheduler_container)

    # --- compose env ---
    @app.get("/compose/engine_env")
    def compose_engine_env() -> Dict[str, Any]:
        return get_service_env(settings.compose_path, settings.compose_service_engine)

    @app.get("/compose/scheduler_env")
    def compose_scheduler_env() -> Dict[str, Any]:
        return get_service_env(settings.compose_path, settings.compose_service_scheduler)

    # --- logs ---
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

    # --- scheduler proxy (upcoming still useful) ---
    @app.get("/scheduler/upcoming")
    async def scheduler_upcoming(n: int = Query(10, ge=1, le=50)) -> JSONResponse:
        data = await sched.upcoming(n=n)
        return JSONResponse(data)

    # --- icecast ---
    @app.get("/icecast/now")
    async def icecast_now() -> JSONResponse:
        data = await ice.now_playing()
        return JSONResponse(data)

    # =========================
    # Panel-friendly endpoints
    # =========================
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

    @app.get("/panel/now")
    async def panel_now() -> Dict[str, Any]:
        ic = await ice.now_playing()
        title = None
        if isinstance(ic, dict) and ic.get("ok"):
            title = ic.get("title") or (ic.get("raw") or {}).get("title")
        return {
            "ok": bool(title),
            "title": title,
            "source": "icecast",
            "mount": settings.icecast_mount,
        }

    @app.get("/panel/upcoming")
    async def panel_upcoming(n: int = Query(10, ge=1, le=30)) -> Dict[str, Any]:
        # current title from icecast
        ic = await ice.now_playing()
        current_title = None
        if isinstance(ic, dict) and ic.get("ok"):
            current_title = ic.get("title")

        upcoming = docker_client.compute_upcoming_from_preprocess(
            engine_container=settings.engine_container,
            current_title=current_title,
            n=n,
            tail=2000,
        )
        return upcoming

    return app
