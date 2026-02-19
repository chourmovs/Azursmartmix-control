from __future__ import annotations

from typing import Any, Dict

import httpx
from nicegui import ui

from azursmartmix_control.config import Settings


class ControlUI:
    """NiceGUI frontend that consumes the local FastAPI endpoints.

    NiceGUI API notes:
    - json_editor: mutate editor.properties['content'] then call editor.update() (no args)
    - badge.set_text(...) returns None (no chaining!)
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_base = settings.api_prefix.rstrip("/")
        self.timeout = httpx.Timeout(2.5, connect=1.5)

        self.status_data: Dict[str, Any] = {}
        self.config_data: Dict[str, Any] = {}
        self.logs_engine: str = ""
        self.logs_sched: str = ""
        self.now_data: Dict[str, Any] = {}
        self.upcoming_data: Dict[str, Any] = {}

        self._lbl_docker = None
        self._lbl_engine = None
        self._lbl_sched = None
        self._json_status = None
        self._json_config = None
        self._json_now = None
        self._json_upcoming = None
        self._logs_engine_box = None
        self._logs_sched_box = None

        self._timer = None

    def build(self) -> None:
        ui.page_title("AzurSmartMix Control (read-only)")

        with ui.header().classes("items-center justify-between"):
            ui.label("AzurSmartMix Control Plane").classes("text-lg font-bold")
            ui.label("v1 read-only").classes("text-sm opacity-80")

        with ui.row().classes("w-full"):
            with ui.card().classes("w-full"):
                ui.label("Runtime status").classes("text-base font-semibold")
                with ui.row().classes("items-center gap-6"):
                    self._lbl_docker = ui.badge("Docker: ?", color="grey")
                    self._lbl_engine = ui.badge("Engine: ?", color="grey")
                    self._lbl_sched = ui.badge("Scheduler: ?", color="grey")

                with ui.row().classes("items-center gap-2"):
                    ui.button("Refresh", on_click=self.refresh_all).props("outline")
                    ui.button("Auto-refresh (2s)", on_click=self.enable_autorefresh).props("outline")
                    ui.button("Stop auto-refresh", on_click=self.disable_autorefresh).props("outline")

                self._json_status = ui.json_editor({"content": {"json": {}}}).classes("w-full")

        with ui.row().classes("w-full"):
            with ui.card().classes("w-1/2"):
                ui.label("Config (read-only YAML)").classes("text-base font-semibold")
                self._json_config = ui.json_editor({"content": {"json": {}}}).classes("w-full")

            with ui.card().classes("w-1/2"):
                ui.label("Now / Upcoming (scheduler proxy)").classes("text-base font-semibold")
                ui.label("Now (best-effort)").classes("text-sm font-semibold mt-2")
                self._json_now = ui.json_editor({"content": {"json": {}}}).classes("w-full")
                ui.label("Upcoming").classes("text-sm font-semibold mt-2")
                self._json_upcoming = ui.json_editor({"content": {"json": {}}}).classes("w-full")

        with ui.row().classes("w-full"):
            with ui.card().classes("w-1/2"):
                ui.label("Engine logs (tail)").classes("text-base font-semibold")
                with ui.row().classes("items-center gap-2"):
                    ui.button("Refresh", on_click=self.refresh_engine_logs).props("outline")
                self._logs_engine_box = ui.textarea(label="", value="").props(
                    "readonly rows=20"
                ).classes("w-full font-mono text-xs")

            with ui.card().classes("w-1/2"):
                ui.label("Scheduler logs (tail)").classes("text-base font-semibold")
                with ui.row().classes("items-center gap-2"):
                    ui.button("Refresh", on_click=self.refresh_scheduler_logs).props("outline")
                self._logs_sched_box = ui.textarea(label="", value="").props(
                    "readonly rows=20"
                ).classes("w-full font-mono text-xs")

        ui.timer(0.1, self.refresh_all, once=True)

    def _set_json(self, editor: Any, payload: Dict[str, Any]) -> None:
        if editor is None:
            return
        editor.properties["content"] = {"json": payload}
        editor.update()

    def _badge_set(self, badge: Any, text: str, color: str) -> None:
        """Set badge text + color without chaining (NiceGUI returns None on set_text)."""
        if badge is None:
            return
        badge.set_text(text)
        badge.props(f"color={color}")

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

    async def refresh_all(self) -> None:
        await self.refresh_status()
        await self.refresh_config()
        await self.refresh_now_upcoming()
        await self.refresh_engine_logs()
        await self.refresh_scheduler_logs()

    async def refresh_status(self) -> None:
        try:
            data = await self._get_json("/status")
            self.status_data = data
            self._set_json(self._json_status, data)
            self._update_badges(data)
        except Exception as e:
            err = {"error": str(e)}
            self._set_json(self._json_status, err)
            self._badge_set(self._lbl_docker, "Docker: error", "red")

    async def refresh_config(self) -> None:
        try:
            data = await self._get_json("/config")
            self.config_data = data
            self._set_json(self._json_config, data)
        except Exception as e:
            self._set_json(self._json_config, {"error": str(e)})

    async def refresh_now_upcoming(self) -> None:
        try:
            now = await self._get_json("/scheduler/now")
            self.now_data = now
            self._set_json(self._json_now, now)
        except Exception as e:
            self._set_json(self._json_now, {"error": str(e)})

        try:
            up = await self._get_json("/scheduler/upcoming?n=10")
            self.upcoming_data = up
            self._set_json(self._json_upcoming, up)
        except Exception as e:
            self._set_json(self._json_upcoming, {"error": str(e)})

    async def refresh_engine_logs(self) -> None:
        try:
            txt = await self._get_text("/logs?service=engine")
            self.logs_engine = txt
            if self._logs_engine_box:
                self._logs_engine_box.set_value(txt)
        except Exception as e:
            if self._logs_engine_box:
                self._logs_engine_box.set_value(f"[ui] error fetching engine logs: {e}\n")

    async def refresh_scheduler_logs(self) -> None:
        try:
            txt = await self._get_text("/logs?service=scheduler")
            self.logs_sched = txt
            if self._logs_sched_box:
                self._logs_sched_box.set_value(txt)
        except Exception as e:
            if self._logs_sched_box:
                self._logs_sched_box.set_value(f"[ui] error fetching scheduler logs: {e}\n")

    def _update_badges(self, data: Dict[str, Any]) -> None:
        docker_ok = bool(data.get("docker_ping"))
        self._badge_set(self._lbl_docker, f"Docker: {'OK' if docker_ok else 'DOWN'}", "green" if docker_ok else "red")

        eng = data.get("engine") or {}
        sch = data.get("scheduler") or {}

        def badge_text(x: Dict[str, Any], label: str) -> str:
            if not x.get("present"):
                return f"{label}: missing"
            st = x.get("status") or "unknown"
            hl = x.get("health")
            return f"{label}: {st} / health={hl}" if hl else f"{label}: {st}"

        if eng.get("present") and eng.get("status") == "running":
            self._badge_set(self._lbl_engine, badge_text(eng, "Engine"), "green")
        elif not eng.get("present"):
            self._badge_set(self._lbl_engine, badge_text(eng, "Engine"), "red")
        else:
            self._badge_set(self._lbl_engine, badge_text(eng, "Engine"), "orange")

        if sch.get("present") and sch.get("status") == "running":
            self._badge_set(self._lbl_sched, badge_text(sch, "Scheduler"), "green")
        elif not sch.get("present"):
            self._badge_set(self._lbl_sched, badge_text(sch, "Scheduler"), "red")
        else:
            self._badge_set(self._lbl_sched, badge_text(sch, "Scheduler"), "orange")

    def enable_autorefresh(self) -> None:
        if self._timer is not None:
            return
        self._timer = ui.timer(2.0, self.refresh_all)

    def disable_autorefresh(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._timer = None
