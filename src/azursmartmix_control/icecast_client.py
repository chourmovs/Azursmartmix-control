# src/azursmartmix_control/icecast_client.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx


class IcecastClient:
    """Read-only Icecast status client (best-effort).

    Default endpoint: /status-json.xsl
    We extract the source matching the configured mount and return:
    - title (if present)
    - artist (if present)
    - listeners, bitrate, server_name, etc. when available
    """

    def __init__(self, scheme: str, host: str, port: int, status_path: str, mount: str) -> None:
        self.scheme = scheme or "http"
        self.host = host
        self.port = int(port)
        self.status_path = status_path or "/status-json.xsl"
        self.mount = mount if mount.startswith("/") else f"/{mount}"
        self.timeout = httpx.Timeout(2.5, connect=1.5)

    def _base(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    async def fetch_status(self) -> Dict[str, Any]:
        url = f"{self._base()}{self.status_path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url)
            r.raise_for_status()
            # Icecast status-json is usually JSON despite .xsl
            try:
                return r.json()
            except Exception:
                return {"raw_text": r.text}

    @staticmethod
    def _iter_sources(payload: Dict[str, Any]):
        icestats = (payload or {}).get("icestats") or {}
        src = icestats.get("source")
        if src is None:
            return []
        if isinstance(src, list):
            return src
        return [src] if isinstance(src, dict) else []

    @staticmethod
    def _as_int_or_none(value: Any) -> Optional[int]:
        try:
            if value is None or value == "":
                return None
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _normalize_mount(value: Any) -> Optional[str]:
        s = str(value or "").strip()
        if not s:
            return None
        if s.startswith("/"):
            return s
        if "://" in s:
            try:
                from urllib.parse import urlparse

                parsed = urlparse(s)
                path = str(parsed.path or "").strip()
                if path:
                    return path if path.startswith("/") else f"/{path}"
            except Exception:
                pass
        return f"/{s}"

    def _source_mount(self, source: Dict[str, Any]) -> Optional[str]:
        if not isinstance(source, dict):
            return None

        mount = self._normalize_mount(source.get("mount"))
        if mount:
            return mount

        listenurl = str(source.get("listenurl") or "").strip()
        if listenurl:
            return self._normalize_mount(listenurl)

        return None

    def _source_public_url(self, source: Dict[str, Any]) -> Optional[str]:
        if not isinstance(source, dict):
            return None

        listenurl = str(source.get("listenurl") or "").strip()
        if listenurl:
            return listenurl

        mount = self._source_mount(source)
        if not mount:
            return None

        return f"{self._base()}{mount}"

    @staticmethod
    def _source_title(source: Dict[str, Any]) -> Optional[str]:
        if not isinstance(source, dict):
            return None
        title = str(source.get("title") or source.get("yp_currently_playing") or "").strip()
        return title or None

    @staticmethod
    def _source_artist(source: Dict[str, Any]) -> Optional[str]:
        if not isinstance(source, dict):
            return None
        artist = str(source.get("artist") or "").strip()
        return artist or None

    @staticmethod
    def _source_format_label(source: Dict[str, Any]) -> Optional[str]:
        if not isinstance(source, dict):
            return None

        raw = " ".join(
            [
                str(source.get("server_type") or ""),
                str(source.get("content_type") or ""),
                str(source.get("audio_info") or ""),
            ]
        ).strip().lower()

        if not raw:
            return None
        if "aac" in raw:
            return "AAC"
        if "mpeg" in raw or "mp3" in raw:
            return "MP3"
        if "ogg" in raw or "vorbis" in raw:
            return "Ogg"
        if "opus" in raw:
            return "Opus"
        if "flac" in raw:
            return "FLAC"
        return None

    def _source_to_mount_item(self, source: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(source, dict):
            return None

        mount = self._source_mount(source)
        if not mount:
            return None

        bitrate = self._as_int_or_none(source.get("bitrate"))
        listeners = self._as_int_or_none(source.get("listeners"))
        listener_peak = self._as_int_or_none(source.get("listener_peak"))
        title = self._source_title(source)
        artist = self._source_artist(source)
        public_url = self._source_public_url(source)
        fmt = self._source_format_label(source)

        if bitrate is not None and fmt:
            display_name = f"{mount} ({bitrate}kbps {fmt})"
        elif bitrate is not None:
            display_name = f"{mount} ({bitrate}kbps)"
        elif fmt:
            display_name = f"{mount} ({fmt})"
        else:
            display_name = mount

        return {
            "mount": mount,
            "display_name": display_name,
            "public_url": public_url,
            "title": title,
            "artist": artist,
            "listeners": listeners,
            "listener_peak": listener_peak,
            "bitrate": bitrate,
            "server_name": str(source.get("server_name") or "").strip() or None,
            "genre": str(source.get("genre") or "").strip() or None,
            "content_type": str(source.get("server_type") or source.get("content_type") or "").strip() or None,
            "format_label": fmt,
            "raw": source,
        }

    def _find_source_for_mount(self, sources: List[Any], mount: str) -> Optional[Dict[str, Any]]:
        wanted = self._normalize_mount(mount)
        if not wanted:
            return None

        for source in sources:
            if not isinstance(source, dict):
                continue
            if self._source_mount(source) == wanted:
                return source

        return None

    async def list_mountpoints(self) -> Dict[str, Any]:
        try:
            payload = await self.fetch_status()
        except Exception as e:
            return {
                "ok": False,
                "source": "icecast",
                "error": str(e),
                "items": [],
                "count": 0,
            }

        items: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for source in self._iter_sources(payload):
            item = self._source_to_mount_item(source if isinstance(source, dict) else {})
            if not item:
                continue

            mount = str(item.get("mount") or "").strip()
            if not mount or mount in seen:
                continue

            seen.add(mount)
            items.append(item)

        items.sort(key=lambda x: str(x.get("mount") or ""))

        return {
            "ok": True,
            "source": "icecast",
            "count": len(items),
            "items": items,
        }

    async def now_playing(self) -> Dict[str, Any]:
        try:
            payload = await self.fetch_status()
        except Exception as e:
            return {
                "ok": False,
                "source": "icecast",
                "error": str(e),
                "mount": self.mount,
            }

        sources = self._iter_sources(payload)
        match = self._find_source_for_mount(sources, self.mount)

        if match is None:
            return {
                "ok": False,
                "source": "icecast",
                "error": "mount not found in status",
                "mount": self.mount,
                "available": [
                    (self._source_mount(s if isinstance(s, dict) else {}) or "unknown")
                    for s in sources
                ],
            }

        title = self._source_title(match)
        artist = self._source_artist(match)

        return {
            "ok": True,
            "source": "icecast",
            "mount": self.mount,
            "title": title,
            "artist": artist,
            "listeners": match.get("listeners"),
            "listener_peak": match.get("listener_peak"),
            "bitrate": match.get("bitrate"),
            "server_name": match.get("server_name"),
            "genre": match.get("genre"),
            "raw": match,
        }
