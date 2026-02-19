from __future__ import annotations

import os
from typing import Any, Dict

import yaml
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from azursmartmix_control.config import Settings
from azursmartmix_control.docker_client import DockerClient
from azursmartmix_control.scheduler_client import SchedulerClient


def _read_text_file(path: str, max_bytes: int = 256_000) -> Dict[str, Any]:
    """Read file as text (best-effort), bounded for safety."""
    if not path:
        return {"present": False, "path": path, "raw_text": None, "error": "empty path"}

    if not os.path.exists(path):
        return {"present": False, "path": path, "raw_text": None, "error": "not found"}

    try:
        with open(path, "rb") as f:
            raw = f.read(max_bytes + 1)
        truncated = len(raw) > max_bytes
        if truncated:
            raw = raw[:max_bytes]
        try:
            txt = raw.decode("utf-8")
        except UnicodeDecodeError:
            txt = raw.decode("utf-8", errors="replace")
        return {"present": True, "path": path, "raw_text": txt, "truncated": truncated, "error": None}
    except Exception as e:
        return {"present": True, "path": path, "raw_text": None, "error": f"read failed: {e}"}


def create_api(settings: Settings) -> FastAPI:
    """Build the FastAPI app providing read-only endpoints."""
    app = FastAPI(title="AzurSmartMix Control API", version="0.1.0")

    docker_client = DockerClient()
    now_ep = os.getenv("SCHED_NOW_ENDPOINT", "").strip() or None
    sched = SchedulerClient(settings.sched_base_url, now_endpoint=now_ep)

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"ok": True}

    @app.get("/status")
    def status() -> Dict[str, Any]:
        return docker_client.runtime_summary(settings.engine_container, settings.scheduler_container)

    @app.get("/config")
    def read_config() -> Dict[str, Any]:
        """
        Read config.yml in read-only mode.

        Important: never 500 in v1.
        - returns parse_ok=false + raw_text + error when YAML is invalid
        """
        base = _read_text_file(settings.config_path)
        if not base.get("present") or base.get("raw_text") is None:
            return {
                "present": bool(base.get("present")),
                "path": base.get("path"),
                "parse_ok": False,
                "data": None,
                "raw_text": base.get("raw_text"),
                "error": base.get("error"),
                "truncated": base.get("truncated", False),
            }

        raw_text = base["raw_text"]
        try:
            data = yaml.safe_load(raw_text)
            return {
                "present": True,
                "path": base.get("path"),
                "parse_ok": True,
                "data": data,
                "raw_text": raw_text,
                "error": None,
                "truncated": base.get("truncated", False),
            }
        except Exception as e:
            return {
                "present": True,
                "path": base.get("path"),
                "parse_ok": False,
                "data": None,
                "raw_text": raw_text,
                "error": f"YAML parse error: {e}",
                "truncated": base.get("truncated", False),
            }

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

    @app.get("/scheduler/health")
    async def scheduler_health() -> JSONResponse:
        data = await sched.health()
        return JSONResponse(data)

    @app.get("/scheduler/now")
    async def scheduler_now() -> JSONResponse:
        data = await sched.now_playing()
        return JSONResponse(data)

    @app.get("/scheduler/upcoming")
    async def scheduler_upcoming(n: int = Query(10, ge=1, le=50)) -> JSONResponse:
        data = await sched.upcoming(n=n)
        return JSONResponse(data)

    @app.get("/now_playing")
    def now_playing() -> JSONResponse:
        """Best-effort now playing inferred from engine logs."""
        data = docker_client.best_effort_now_playing_from_logs(settings.engine_container)
        return JSONResponse(data)

    return app
