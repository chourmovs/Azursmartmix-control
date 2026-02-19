from __future__ import annotations

from typing import Any, Dict, Optional

import httpx


class SchedulerClient:
    """Proxy client to AzurSmartMix scheduler API.

    v1: scheduler has /health and /next.
    Now-playing endpoints are NOT assumed to exist.
    If you later add one, set env SCHED_NOW_ENDPOINT (e.g. "/now").
    """

    def __init__(self, base_url: str, now_endpoint: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(2.5, connect=1.5)
        self.now_endpoint = (now_endpoint or "").strip() or None

    async def health(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(f"{self.base_url}/health")
            r.raise_for_status()
            data = self._safe_json(r)
            return data if isinstance(data, dict) else {"ok": True, "raw": data}

    async def now_playing(self) -> Dict[str, Any]:
        """Now playing via scheduler IF configured.

        By default returns a note (no probes, no log spam).
        """
        if not self.now_endpoint:
            return {
                "source": None,
                "data": {"note": "Scheduler now-playing endpoint not configured (v1)."},
            }

        data = await self._try_get_json(self.now_endpoint)
        if data is None:
            return {
                "source": self.now_endpoint,
                "data": {"note": "Configured scheduler now endpoint returned error/404."},
            }
        return {"source": self.now_endpoint, "data": data}

    async def upcoming(self, n: int = 10) -> Dict[str, Any]:
        """Best-effort upcoming queue."""
        # Prefer /next?n=...
        data = await self._try_get_json(f"/next?n={n}")
        if data is not None:
            return {"source": f"/next?n={n}", "data": data}

        # Fallback /next10 style
        data = await self._try_get_json(f"/next{n}")
        if data is not None:
            return {"source": f"/next{n}", "data": data}

        # Minimal fallback /next1
        data = await self._try_get_json("/next1")
        if data is not None:
            return {"source": "/next1", "data": data}

        return {"source": None, "data": {"note": "No upcoming endpoint found on scheduler."}}

    async def _try_get_json(self, path: str) -> Optional[Any]:
        p = path if path.startswith("/") else f"/{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                r = await client.get(f"{self.base_url}{p}")
                if r.status_code >= 400:
                    return None
                return self._safe_json(r)
            except Exception:
                return None

    @staticmethod
    def _safe_json(r: httpx.Response) -> Any:
        ct = (r.headers.get("content-type") or "").lower()
        if "application/json" in ct:
            try:
                return r.json()
            except Exception:
                return {"raw_text": r.text}
        txt = r.text.strip()
        return {"raw_text": txt} if txt else {}
