from __future__ import annotations

import math
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from azursmartmix_control.compose_reader import (
    get_env_from_host_envfile,
    get_service_env,
    set_env_in_host_envfile,
)
from azursmartmix_control.config import Settings
from azursmartmix_control.docker_client import DockerClient
from azursmartmix_control.icecast_client import IcecastClient
from azursmartmix_control.runtime_queue_state import get_state
from azursmartmix_control.scheduler_client import SchedulerClient


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

    az_session = requests.Session()

    def _az_base_url() -> str:
        return str(settings.azuracast_base_url or "").strip().rstrip("/")

    def _az_headers() -> Dict[str, str]:
        headers: Dict[str, str] = {"Accept": "application/json"}
        api_key = str(settings.azuracast_api_key or "").strip()
        if api_key:
            headers["X-API-Key"] = api_key
        return headers

    def _az_get_json(path: str) -> Any:
        base_url = _az_base_url()
        if not base_url:
            raise RuntimeError("AZURACAST_BASE_URL is empty")

        url = f"{base_url}{path}"
        r = az_session.get(
            url,
            headers=_az_headers(),
            timeout=float(settings.azuracast_timeout_s),
            verify=bool(settings.azuracast_verify_tls),
        )
        if r.status_code >= 400:
            raise RuntimeError(f"AzuraCast API error {r.status_code} for {url}: {r.text[:500]}")
        return r.json() if r.content else []

    def _as_records_list(payload: Any) -> List[Any]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("records", "rows", "data", "result", "items"):
                val = payload.get(key)
                if isinstance(val, list):
                    return val
        raise ValueError("Unexpected AzuraCast payload shape; expected list-like response")

    def _as_int_or_none(value: Any) -> Optional[int]:
        try:
            if value is None or value == "":
                return None
            return int(value)
        except Exception:
            return None

    def _as_float_or_none(value: Any) -> Optional[float]:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:
            return None

    def _as_bool_default(value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        s = str(value).strip().lower()
        if s in {"1", "true", "yes", "on"}:
            return True
        if s in {"0", "false", "no", "off"}:
            return False
        return default

    def _safe_str(value: Any) -> Optional[str]:
        s = str(value or "").strip()
        return s or None

    def _playlist_to_panel(item: Dict[str, Any]) -> Dict[str, Any]:
        links = item.get("links") if isinstance(item.get("links"), dict) else {}
        export = links.get("export") if isinstance(links.get("export"), dict) else {}

        playlist_id = _as_int_or_none(item.get("id"))
        num_songs = _as_int_or_none(item.get("num_songs"))
        weight = _as_int_or_none(item.get("weight"))

        return {
            "id": playlist_id,
            "name": str(item.get("name") or "").strip(),
            "short_name": str(item.get("short_name") or item.get("shortName") or "").strip() or None,
            "slug": str(item.get("slug") or "").strip() or None,
            "type": str(item.get("type") or "").strip() or None,
            "source": str(item.get("source") or "").strip() or None,
            "order": str(item.get("order") or "").strip() or None,
            "weight": weight,
            "is_enabled": bool(item.get("is_enabled") if item.get("is_enabled") is not None else True),
            "is_jingle": bool(item.get("is_jingle") if item.get("is_jingle") is not None else False),
            "num_songs": num_songs,
            "backend_options": item.get("backend_options") if isinstance(item.get("backend_options"), dict) else None,
            "schedule_items": item.get("schedule_items") if isinstance(item.get("schedule_items"), list) else [],
            "links": links if links else None,
            "export_m3u": str(export.get("m3u") or item.get("export_m3u") or item.get("exportM3U") or "").strip() or None,
            "export_pls": str(export.get("pls") or item.get("export_pls") or item.get("exportPLS") or "").strip() or None,
        }

    def _normalize_playlist_refs(value: Any) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        if not isinstance(value, list):
            return out

        for it in value:
            if isinstance(it, dict):
                pid = _as_int_or_none(it.get("id"))
                name = _safe_str(it.get("name") or it.get("text") or it.get("label"))
                short_name = _safe_str(it.get("short_name") or it.get("shortName"))
                out.append(
                    {
                        "id": pid,
                        "name": name,
                        "short_name": short_name,
                    }
                )
            else:
                name = _safe_str(it)
                if name:
                    out.append({"id": None, "name": name, "short_name": None})
        return out

    def _media_to_panel(item: Dict[str, Any]) -> Dict[str, Any]:
        links = item.get("links") if isinstance(item.get("links"), dict) else {}

        playlists = _normalize_playlist_refs(
            item.get("playlists")
            or item.get("playlist_refs")
            or item.get("playlistRefs")
        )

        playlist_ids = [p["id"] for p in playlists if p.get("id") is not None]
        playlist_names = [p["name"] for p in playlists if p.get("name")]

        length = (
            _as_float_or_none(item.get("length"))
            or _as_float_or_none(item.get("duration"))
            or _as_float_or_none(item.get("length_seconds"))
            or _as_float_or_none(item.get("duration_seconds"))
        )

        media_id = (
            _as_int_or_none(item.get("id"))
            or _as_int_or_none(item.get("media_id"))
            or _as_int_or_none(item.get("mediaId"))
            or _as_int_or_none(item.get("song_id"))
            or _as_int_or_none(item.get("songId"))
        )

        path = _safe_str(
            item.get("path")
            or item.get("file")
            or item.get("file_path")
            or item.get("relative_path")
            or item.get("basename")
        )

        title = _safe_str(item.get("title"))
        artist = _safe_str(item.get("artist"))
        album = _safe_str(item.get("album"))

        # Conservative fallback: if title missing, derive from path basename.
        if not title and path:
            title = DockerClient.display_title(os.path.basename(path))

        return {
            "id": media_id,
            "path": path,
            "title": title,
            "title_display": title,
            "artist": artist,
            "album": album,
            "length": length,
            "length_text": _safe_str(item.get("length_text") or item.get("duration_text")),
            "is_public": _as_bool_default(item.get("is_public"), default=False),
            "playlists": playlists,
            "playlist_ids": playlist_ids,
            "playlist_names": playlist_names,
            "links": links if links else None,
            "raw_exists": item.get("exists"),
        }

    def _mount_to_panel(item: Dict[str, Any]) -> Dict[str, Any]:
        mount_id = _as_int_or_none(item.get("id"))
        bitrate = _as_int_or_none(item.get("bitrate"))
        listeners = _as_int_or_none(item.get("listeners"))

        return {
            "id": mount_id,
            "name": _safe_str(item.get("name")),
            "display_name": _safe_str(item.get("display_name") or item.get("displayName")),
            "path": _safe_str(item.get("path")),
            "format": _safe_str(item.get("format")),
            "bitrate": bitrate,
            "listeners": listeners,
            "is_default": _as_bool_default(item.get("is_default"), default=False),
            "is_public": _as_bool_default(item.get("is_public"), default=False),
            "intro_url": _safe_str(item.get("intro_url")),
            "fallback_mount": _safe_str(item.get("fallback_mount")),
            "relay_url": _safe_str(item.get("relay_url")),
            "links": item.get("links") if isinstance(item.get("links"), dict) else None,
        }

    def _media_matches_query(item: Dict[str, Any], q: str) -> bool:
        if not q:
            return True
        needle = q.casefold()
        hay = " ".join(
            [
                str(item.get("path") or ""),
                str(item.get("title") or ""),
                str(item.get("artist") or ""),
                str(item.get("album") or ""),
                " ".join([str(x or "") for x in (item.get("playlist_names") or [])]),
            ]
        ).casefold()
        return needle in hay

    def _media_matches_playlist(item: Dict[str, Any], playlist_id: Optional[int]) -> bool:
        if playlist_id is None:
            return True
        ids = item.get("playlist_ids") or []
        return playlist_id in ids

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

    def _runtime_state() -> Dict[str, Any]:
        try:
            data = get_state()
        except Exception:
            data = {"now": None, "queue": [], "history": []}
        if not isinstance(data, dict):
            return {"now": None, "queue": [], "history": []}
        now = data.get("now")
        queue = data.get("queue")
        history = data.get("history")
        return {
            "now": now if isinstance(now, dict) else None,
            "queue": queue if isinstance(queue, list) else [],
            "history": history if isinstance(history, list) else [],
        }

    def _runtime_entry_to_panel(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(entry, dict):
            return None

        title_raw = str(entry.get("title") or "").strip()
        path_raw = str(entry.get("path") or "").strip()
        source_path_raw = str(entry.get("source_path") or "").strip()
        playlist_raw = str(entry.get("playlist") or "").strip()

        title = _display_title_or_none(title_raw)
        if not title and source_path_raw:
            title = _display_title_or_none(os.path.basename(source_path_raw))
        if not title and path_raw:
            title = _display_title_or_none(os.path.basename(path_raw))
        if not title:
            return None

        bpm = entry.get("bpm")
        try:
            bpm = float(bpm) if bpm is not None else None
        except Exception:
            bpm = None

        ts = entry.get("ts")
        try:
            ts = float(ts) if ts is not None else None
        except Exception:
            ts = None

        return {
            "title": title,
            "title_display": title,
            "playlist": playlist_raw or None,
            "bpm": bpm,
            "ts": ts,
            "ts_iso_utc": (
                datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")
                if ts is not None else None
            ),
            "path": path_raw or None,
            "source_path": source_path_raw or None,
        }

    def _runtime_now_panel() -> Optional[Dict[str, Any]]:
        st = _runtime_state()
        return _runtime_entry_to_panel(st.get("now") or {})

    def _runtime_queue_panel(limit: int) -> List[Dict[str, Any]]:
        st = _runtime_state()
        raw = st.get("queue") or []
        out: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for item in raw:
            ent = _runtime_entry_to_panel(item if isinstance(item, dict) else {})
            if not ent:
                continue
            norm = docker_client.normalize_title(str(ent.get("title") or ""))
            if norm and norm in seen:
                continue
            if norm:
                seen.add(norm)
            out.append(ent)
            if len(out) >= limit:
                break

        return out

    def _runtime_history_panel(limit: int) -> List[Dict[str, Any]]:
        st = _runtime_state()
        raw = st.get("history") or []
        out: List[Dict[str, Any]] = []

        for item in reversed(raw):
            ent = _runtime_entry_to_panel(item if isinstance(item, dict) else {})
            if not ent:
                continue
            out.append(ent)
            if len(out) >= limit:
                break

        return out

    def _merge_upcoming_sources(
        primary: List[Dict[str, Any]],
        secondary: List[Dict[str, Any]],
        limit: int,
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for seq in (primary, secondary):
            if not isinstance(seq, list):
                continue
            for item in seq:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or item.get("title_display") or "").strip()
                norm = docker_client.normalize_title(title)
                if not norm or norm in seen:
                    continue
                seen.add(norm)
                out.append(item)
                if len(out) >= limit:
                    return out

        return out

    @app.get("/runtime/queue")
    def runtime_queue():
        return get_state()

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"ok": True}

    @app.get("/status")
    def status() -> Dict[str, Any]:
        return docker_client.runtime_summary(settings.engine_container, settings.scheduler_container)

    @app.get("/azuracast/playlists")
    def azuracast_playlists() -> Dict[str, Any]:
        station_id = int(settings.azuracast_station_id)

        try:
            payload = _az_get_json(f"/api/station/{station_id}/playlists")
            rows = _as_records_list(payload)
            items = [_playlist_to_panel(it) for it in rows if isinstance(it, dict)]
            return {
                "ok": True,
                "source": "azuracast_api",
                "station_id": station_id,
                "total": len(items),
                "items": items,
            }
        except Exception as e:
            return {
                "ok": False,
                "source": "azuracast_api",
                "station_id": station_id,
                "total": 0,
                "items": [],
                "error": str(e),
            }

    @app.get("/azuracast/media")
    def azuracast_media(
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=50, ge=1, le=200),
        q: str = Query(default=""),
        playlist_id: Optional[int] = Query(default=None),
    ) -> Dict[str, Any]:
        station_id = int(settings.azuracast_station_id)

        try:
            payload = _az_get_json(f"/api/station/{station_id}/files")
            rows = _as_records_list(payload)
            all_items = [_media_to_panel(it) for it in rows if isinstance(it, dict)]

            q_norm = str(q or "").strip()
            filtered = [
                it for it in all_items
                if _media_matches_query(it, q_norm) and _media_matches_playlist(it, playlist_id)
            ]

            total = len(filtered)
            total_pages = max(1, int(math.ceil(total / page_size))) if total > 0 else 1
            page_eff = min(page, total_pages)
            start = (page_eff - 1) * page_size
            end = start + page_size
            page_items = filtered[start:end]

            return {
                "ok": True,
                "source": "azuracast_api",
                "station_id": station_id,
                "page": page_eff,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
                "query": q_norm or None,
                "playlist_id": playlist_id,
                "items": page_items,
            }
        except Exception as e:
            return {
                "ok": False,
                "source": "azuracast_api",
                "station_id": station_id,
                "page": page,
                "page_size": page_size,
                "total": 0,
                "total_pages": 0,
                "query": str(q or "").strip() or None,
                "playlist_id": playlist_id,
                "items": [],
                "error": str(e),
            }

    @app.get("/azuracast/mountpoints")
    def azuracast_mountpoints() -> Dict[str, Any]:
        station_id = int(settings.azuracast_station_id)

        try:
            payload = _az_get_json(f"/api/station/{station_id}/mounts")
            rows = _as_records_list(payload)
            items = [_mount_to_panel(it) for it in rows if isinstance(it, dict)]
            return {
                "ok": True,
                "source": "azuracast_api",
                "station_id": station_id,
                "total": len(items),
                "items": items,
            }
        except Exception as e:
            return {
                "ok": False,
                "source": "azuracast_api",
                "station_id": station_id,
                "total": 0,
                "items": [],
                "error": str(e),
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
        return JSONResponse(data)

    @app.get("/panel/engine_env")
    def panel_engine_env() -> Dict[str, Any]:
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
                    "bpm": sched_entry.get("bpm"),
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

        runtime_now = _runtime_now_panel()
        runtime_upcoming = _runtime_queue_panel(limit=6)

        title_effective = runtime_now.get("title") if isinstance(runtime_now, dict) else None
        now_source = "runtime_queue_state" if title_effective else None

        if not title_effective:
            title_effective = icecast_title
            now_source = "icecast_metadata" if icecast_title else None

        upcoming_tempo = _strict_tempo_upcoming(current_title=title_effective, n=6)

        playlist_effective = runtime_now.get("playlist") if isinstance(runtime_now, dict) else None
        pl_observed = {"ok": True, "playlist": playlist_effective, "match": "runtime_queue_state"} if playlist_effective else (
            docker_client.infer_playlist_for_title_from_scheduler(
                scheduler_container=settings.scheduler_container,
                current_title=title_effective,
                tail=3000,
            ) if title_effective else {"ok": True, "playlist": None, "match": None}
        )

        if not playlist_effective:
            playlist_effective = pl_observed.get("playlist") if isinstance(pl_observed, dict) else None

        predicted_next = None
        if isinstance(runtime_upcoming, list) and runtime_upcoming:
            predicted_next = runtime_upcoming[0]
        else:
            tempo_items = upcoming_tempo.get("upcoming") if isinstance(upcoming_tempo, dict) else None
            if isinstance(tempo_items, list) and tempo_items:
                predicted_next = tempo_items[0]

        ss = docker_client.last_engine_stream_start(
            engine_container=settings.engine_container,
            tail=1000,
            recent_window_s=12,
        )

        tempo_items = upcoming_tempo.get("upcoming") if isinstance(upcoming_tempo, dict) else None

        return {
            "ok": bool(title_effective),
            "mount": settings.icecast_mount,
            "source": "runtime_queue_state+icecast(metadata_only)+engine_tempo(select_ok_after_current)+engine(STREAM_START)",
            "now_source": now_source,
            "title_effective": title_effective,
            "playlist_effective": playlist_effective,
            "title_observed": icecast_title,
            "title_runtime": (runtime_now.get("title") if isinstance(runtime_now, dict) else None),
            "playlist_observed": playlist_effective,
            "playlist_runtime": (runtime_now.get("playlist") if isinstance(runtime_now, dict) else None),
            "bpm_runtime": (runtime_now.get("bpm") if isinstance(runtime_now, dict) else None),
            "scheduler_match_observed": pl_observed.get("match") if isinstance(pl_observed, dict) else None,
            "engine_stream_start": ss,
            "tempo_runtime": tempo_runtime,
            "predicted_next": predicted_next,
            "debug": {
                "icecast_ok": bool(isinstance(ic, dict) and ic.get("ok")),
                "icecast_error": (ic.get("error") if isinstance(ic, dict) else None),
                "runtime_now": runtime_now,
                "runtime_upcoming_count": len(runtime_upcoming or []) if isinstance(runtime_upcoming, list) else 0,
                "upcoming_primary_source": (
                    "runtime_queue_state"
                    if isinstance(runtime_upcoming, list) and runtime_upcoming
                    else (upcoming_tempo.get("source") if isinstance(upcoming_tempo, dict) else None)
                ),
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

        runtime_now = _runtime_now_panel()
        runtime_queue = _runtime_queue_panel(limit=n)

        current_title = None
        title_source = None

        if isinstance(runtime_now, dict) and runtime_now.get("title"):
            current_title = runtime_now.get("title")
            title_source = "runtime_queue_state"
        elif icecast_title:
            current_title = icecast_title
            title_source = "icecast_metadata"

        upcoming_tempo = _strict_tempo_upcoming(current_title=current_title, n=n)

        tempo_items = upcoming_tempo.get("upcoming") if isinstance(upcoming_tempo, dict) else []
        if not isinstance(tempo_items, list):
            tempo_items = []

        chosen = _merge_upcoming_sources(
            primary=runtime_queue,
            secondary=tempo_items,
            limit=n,
        )

        primary_source: Optional[str]
        secondary_source: Optional[str]
        used_source: str

        if runtime_queue and tempo_items:
            primary_source = "runtime_queue_state"
            secondary_source = upcoming_tempo.get("source") if isinstance(upcoming_tempo, dict) else None
            used_source = "runtime_queue_plus_tempo_fill"
        elif runtime_queue:
            primary_source = "runtime_queue_state"
            secondary_source = None
            used_source = "runtime_queue_only"
        else:
            primary_source = upcoming_tempo.get("source") if isinstance(upcoming_tempo, dict) else None
            secondary_source = None
            used_source = "tempo_accept_strict"

        return {
            "ok": True,
            "current_title_observed": current_title,
            "source": {
                "primary": primary_source,
                "secondary": secondary_source,
            },
            "upcoming": chosen[:n],
            "debug": {
                "title_source": title_source,
                "icecast_ok": bool(isinstance(ic, dict) and ic.get("ok")),
                "icecast_error": (ic.get("error") if isinstance(ic, dict) else None),
                "runtime_now": runtime_now,
                "runtime_queue_count": len(runtime_queue),
                "tempo_runtime": tempo_runtime,
                "tempo_accept": upcoming_tempo,
                "tempo_items_count": len(tempo_items),
                "used_source": used_source,
            },
        }

    @app.get("/panel/previous")
    def panel_previous() -> Dict[str, Any]:
        items = _runtime_history_panel(limit=1)
        previous = items[0] if items else None

        return {
            "ok": previous is not None,
            "source": "runtime_queue_state_history",
            "previous": previous,
        }

    @app.get("/panel/dashboard")
    async def panel_dashboard(
        upcoming_n: int = Query(10, ge=1, le=30),
        include_logs: bool = Query(default=False),
        engine_log_tail: int = Query(default=200, ge=1, le=2000),
        scheduler_log_tail: int = Query(default=200, ge=1, le=2000),
    ) -> Dict[str, Any]:
        resources = panel_resources()
        runtime = panel_runtime()
        now = await panel_now()
        upcoming = await panel_upcoming(n=upcoming_n)

        payload: Dict[str, Any] = {
            "ok": True,
            "resources": resources,
            "runtime": runtime,
            "now": now,
            "upcoming": upcoming,
        }

        if include_logs:
            eng_tail = max(1, min(engine_log_tail, settings.log_tail_lines_max))
            sch_tail = max(1, min(scheduler_log_tail, settings.log_tail_lines_max))

            payload["logs"] = {
                "engine": docker_client.tail_logs(
                    name=settings.engine_container,
                    tail=eng_tail,
                ),
                "scheduler": docker_client.tail_logs(
                    name=settings.scheduler_container,
                    tail=sch_tail,
                ),
            }

        return payload

    return app
