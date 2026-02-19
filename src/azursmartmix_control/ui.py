from __future__ import annotations

from typing import Any, Dict, List, Tuple

import httpx
from nicegui import ui

from azursmartmix_control.config import Settings


class ControlUI:
    """NiceGUI panel UI (human-friendly)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_base = settings.api_prefix.rstrip("/")
        self.timeout = httpx.Timeout(2.5, connect=1.5)

        self._timer = None

        # runtime widgets
        self._rt_docker = None
        self._rt_engine = None
        self._rt_sched = None

        # config (compose env)
        self._env_table = None
        self._env_rows: List[Dict[str, str]] = []

        # now / upcoming
        self._now_title = None
        self._up_container = None  # column container for upcoming labels

        # logs
        self._logs_engine_box = None
        self._logs_sched_box = None

    def build(self) -> None:
        ui.page_title("AzurSmartMix Control")

        with ui.header().classes("items-center justify-between"):
            ui.label("AzurSmartMix Control Plane").classes("text-lg font-bold")
            with ui.row().classes("items-center gap-2"):
                ui.button("Refresh", on_click=self.refresh_all).props("unelevated")
                ui.button("Auto 5s", on_click=self.enable_autorefresh).props("outline")
                ui.button("Stop", on_click=self.disable_autorefresh).props("outline")

        # Row 1: Runtime cards
        with ui.row().classes("w-full gap-4"):
            with ui.card().classes("w-full"):
                ui.label("Runtime Status").classes("text-base font-semibold")
                with ui.row().classes("items-center gap-3 mt-2"):
                    self._rt_docker = ui.badge("Docker: ?", color="grey")
                with ui.row().classes("w-full gap-4 mt-2"):
                    self._rt_engine = self._build_runtime_card("Engine")
                    self._rt_sched = self._build_runtime_card("Scheduler")

        # Row 2: Config + Now
        with ui.row().classes("w-full gap-4"):
            with ui.card().classes("w-1/2"):
                ui.label("Engine env (docker-compose)").classes("text-base font-semibold")
                ui.label(f"Source: {self.settings.compose_path} / service: {self.settings.compose_service_engine}").classes(
                    "text-xs opacity-70"
                )

                self._env_table = ui.table(
                    columns=[
                        {"name": "key", "label": "KEY", "field": "key", "align": "left"},
                        {"name": "value", "label": "VALUE", "field": "value", "align": "left"},
                    ],
                    rows=[],
                    row_key="key",
                ).classes("w-full")
                self._env_table.props("dense flat bordered")
                self._env_table.style("font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;")

            with ui.card().classes("w-1/2"):
                ui.label("Now Playing").classes("text-base font-semibold")
                self._now_title = ui.label("—").classes("text-xl font-bold mt-2")
                ui.label(f"Mount: {self.settings.icecast_mount}").classes("text-xs opacity-70 mt-1")

        # Row 3: Upcoming
        with ui.row().classes("w-full gap-4"):
            with ui.card().classes("w-full"):
                ui.label("Upcoming (from engine preprocess log)").classes("text-base font-semibold")
                self._up_container = ui.column().classes("mt-2 gap-1")

        # Row 4: Logs
        with ui.row().classes("w-full gap-4"):
            with ui.card().classes("w-1/2"):
                ui.label("Engine logs (tail)").classes("text-base font-semibold")
                with ui.row().classes("items-center gap-2"):
                    ui.button("Refresh", on_click=self.refresh_engine_logs).props("outline")
                self._logs_engine_box = ui.textarea(value="").props("readonly rows=18").classes("w-full font-mono text-xs")

            with ui.card().classes("w-1/2"):
                ui.label("Scheduler logs (tail)").classes("text-base font-semibold")
                with ui.row().classes("items-center gap-2"):
                    ui.button("Refresh", on_click=self.refresh_scheduler_logs).props("outline")
                self._logs_sched_box = ui.textarea(value="").props("readonly rows=18").classes("w-full font-mono text-xs")

        ui.timer(0.1, self.refresh_all, once=True)

    def _build_runtime_card(self, title: str):
        card = ui.card().classes("w-1/2")
        with card:
            ui.label(title).classes("text-sm font-semibold opacity-80")
            name = ui.label("name: —").classes("text-sm")
            image = ui.label("image: —").classes("text-sm")
            status = ui.label("status: —").classes("text-sm")
            health = ui.label("health: —").classes("text-sm")
            uptime = ui.label("uptime: —").classes("text-sm")
        return {"name": name, "image": image, "status": status, "health": health, "uptime": uptime}

    async def _get_json(self, path: str) -> Dict[str, Any]:
        url = f"http://127.0.0.1:{self.settings.ui_port}{self.api_base}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, dict) else {"data": data}

    async def _get_text(self, path: str) -> str:
        url = f"http://127.0.0.1:{self.settings.ui_port}{self.api_base}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.text

    def _badge_set(self, badge, text: str, color: str) -> None:
        if badge is None:
            return
        badge.set_text(text)
        badge.props(f"color={color}")

    async def refresh_all(self) -> None:
        await self.refresh_runtime()
        await self.refresh_engine_env()
        await self.refresh_now()
        await self.refresh_upcoming()
        await self.refresh_engine_logs()
        await self.refresh_scheduler_logs()

    async def refresh_runtime(self) -> None:
        try:
            rt = await self._get_json("/panel/runtime")
        except Exception as e:
            self._badge_set(self._rt_docker, f"Docker: error ({e})", "red")
            return

        docker_ok = bool(rt.get("docker_ping"))
        self._badge_set(self._rt_docker, f"Docker: {'OK' if docker_ok else 'DOWN'}", "green" if docker_ok else "red")

        self._fill_runtime_card(self._rt_engine, rt.get("engine") or {})
        self._fill_runtime_card(self._rt_sched, rt.get("scheduler") or {})

    def _fill_runtime_card(self, w: Dict[str, Any], data: Dict[str, Any]) -> None:
        if not w:
            return
        if not data.get("present"):
            w["name"].set_text(f"name: {data.get('name')}")
            w["image"].set_text("image: -")
            w["status"].set_text("status: missing")
            w["health"].set_text("health: -")
            w["uptime"].set_text("uptime: -")
            return

        w["name"].set_text(f"name: {data.get('name')}")
        w["image"].set_text(f"image: {data.get('image')}")
        w["status"].set_text(f"status: {data.get('status')}")
        w["health"].set_text(f"health: {data.get('health') or '-'}")
        w["uptime"].set_text(f"uptime: {data.get('uptime') or '-'}")

    async def refresh_engine_env(self) -> None:
        if self._env_table is None:
            return
        try:
            data = await self._get_json("/panel/engine_env")
            env = data.get("environment") if isinstance(data, dict) else None
            if not isinstance(env, dict):
                rows = [{"key": "error", "value": str(data)}]
            else:
                # stable ordering
                rows = [{"key": k, "value": str(env.get(k, ""))} for k in sorted(env.keys())]
            self._env_table.rows = rows
            self._env_table.update()
        except Exception as e:
            self._env_table.rows = [{"key": "error", "value": str(e)}]
            self._env_table.update()

    async def refresh_now(self) -> None:
        try:
            now = await self._get_json("/panel/now")
            title = now.get("title") or "—"
            self._now_title.set_text(title)
        except Exception as e:
            self._now_title.set_text(f"Error: {e}")

    async def refresh_upcoming(self) -> None:
        if self._up_container is None:
            return

        try:
            up = await self._get_json("/panel/upcoming?n=10")
            titles = up.get("upcoming") or []
            if not isinstance(titles, list):
                titles = []
        except Exception as e:
            titles = [f"Error: {e}"]

        self._up_container.clear()
        with self._up_container:
            if not titles:
                ui.label("—").classes("text-sm opacity-70")
                return
            for i, t in enumerate(titles, start=1):
                ui.label(f"{i}. {t}").classes("text-sm")

    async def refresh_engine_logs(self) -> None:
        try:
            txt = await self._get_text("/logs?service=engine&tail=200")
            self._logs_engine_box.set_value(txt)
        except Exception as e:
            self._logs_engine_box.set_value(f"[ui] error: {e}\n")

    async def refresh_scheduler_logs(self) -> None:
        try:
            txt = await self._get_text("/logs?service=scheduler&tail=200")
            self._logs_sched_box.set_value(txt)
        except Exception as e:
            self._logs_sched_box.set_value(f"[ui] error: {e}\n")

    def enable_autorefresh(self) -> None:
        if self._timer is not None:
            return
        self._timer = ui.timer(5.0, self.refresh_all)

    def disable_autorefresh(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._timer = None
