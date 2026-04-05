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
    def _mount_from_source(source: Dict[str, Any]) -> Optional[str]:
        mount = str(source.get("mount") or "").strip()
        if mount:
            return mount if mount.startswith("/") else f"/{mount}"

        listenurl = str(source.get("listenurl") or "").strip()
        if listenurl:
            try:
                # Icecast direct mounts usually end with /mount.ext
                if "://" in listenurl:
                    path = listenurl.split("://", 1)[1]
                    path = "/" + path.split("/", 1)[1] if "/" in path else ""
                else:
                    path = listenurl
                path = path.strip()
                return path or None
            except Exception:
                return None

        return None

    @staticmethod
    def _item_from_source(source: Dict[str, Any]) -> Dict[str, Any]:
        mount = IcecastClient._mount_from_source(source) or "unknown"
        title = source.get("title") or source.get("yp_currently_playing") or None
        artist = source.get("artist") or None

        listeners = source.get("listeners")
        try:
            listeners = int(listeners) if listeners not in (None, "") else 0
        except Exception:
            listeners = 0

        bitrate = source.get("bitrate")
        try:
            bitrate = int(bitrate) if bitrate not in (None, "") else None
        except Exception:
            bitrate = None

        return {
            "mount": mount,
            "title": title,
            "artist": artist,
            "listeners": listeners,
            "listener_peak": source.get("listener_peak"),
            "bitrate": bitrate,
            "server_name": source.get("server_name"),
            "genre": source.get("genre"),
            "listenurl": source.get("listenurl"),
            "raw": source,
        }

    async def list_mounts(self) -> Dict[str, Any]:
        try:
            payload = await self.fetch_status()
        except Exception as e:
            return {
                "ok": False,
                "source": "icecast",
                "error": str(e),
                "items": [],
            }

        items: List[Dict[str, Any]] = []
        for source in self._iter_sources(payload):
            if not isinstance(source, dict):
                continue
            items.append(self._item_from_source(source))

        return {
            "ok": True,
            "source": "icecast",
            "count": len(items),
            "items": items,
        }

    async def now_playing(self) -> Dict[str, Any]:
        mounts = await self.list_mounts()
        if not mounts.get("ok"):
            return {
                "ok": False,
                "source": "icecast",
                "error": mounts.get("error"),
                "mount": self.mount,
            }

        match = None
        for item in mounts.get("items") or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("mount") or "") == self.mount:
                match = item
                break

        if match is None:
            return {
                "ok": False,
                "source": "icecast",
                "error": "mount not found in status",
                "mount": self.mount,
                "available": [
                    str(it.get("mount") or "unknown")
                    for it in (mounts.get("items") or [])
                    if isinstance(it, dict)
                ],
            }

        return {
            "ok": True,
            "source": "icecast",
            "mount": self.mount,
            "title": match.get("title"),
            "artist": match.get("artist"),
            "listeners": match.get("listeners"),
            "listener_peak": match.get("listener_peak"),
            "bitrate": match.get("bitrate"),
            "server_name": match.get("server_name"),
            "genre": match.get("genre"),
            "raw": match.get("raw"),
        }
