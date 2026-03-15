from __future__ import annotations

from typing import Any, Dict, List, Optional

import html
import urllib.parse

import httpx
from nicegui import ui

from azursmartmix_control.config import Settings
from azursmartmix_control.ui_assets import AZURA_CSS, AZURA_JS
from azursmartmix_control.ui_dashboard import DashboardMixin
from azursmartmix_control.ui_settings import SettingsMixin


class ControlUI(SettingsMixin, DashboardMixin):
    """AzurSmartMix Control UI.

    Dashboard: Engine env frame removed (as requested).
    Settings: values come from azuramix.env (via compose endpoints),
              layout comes from azursmartmix_env_reference_v2.csv.
    """

    _BOOL_TRUE_WORD = {"true", "yes", "y", "on", "enabled"}
    _BOOL_FALSE_WORD = {"false", "no", "n", "off", "disabled"}
    _BOOL_NUM = {"0", "1"}

    _BOOL_KEY_SUFFIXES = (
        "_ENABLE",
        "_ENABLED",
        "_DISABLE",
        "_DISABLED",
        "_DEBUG",
        "_VERBOSE",
        "_MUTE",
        "_ACCESS_LOG",
        "_LOG",
        "_LOGS",
        "_SINGLE_SEGMENT",
        "_SAFE",
        "_STRICT",
        "_FORCE",
        "_DRYRUN",
        "_DRY_RUN",
        "_MERGE",
        "_SHUFFLE",
        "_LOOP",
        "_LOOP_ONCE",
    )
    _BOOL_KEY_CONTAINS = (
        "_ENABLE_",
        "_ENABLED_",
        "_DISABLE_",
        "_DISABLED_",
        "_DEBUG_",
        "_ACCESS_LOG_",
    )

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_base = settings.api_prefix.rstrip("/")
        self.timeout = httpx.Timeout(30.0, connect=3.0)

        self._timer = None

        self._docker_badge = None
        self._rt_engine_tbl = None
        self._rt_sched_tbl = None

        self._res_cpu_html = None
        self._res_mem_html = None
        self._res_host_meta = None

        self._now_title = None
        self._now_meta = None
        self._now_player = None
        self._now_sources = None

        self._up_list_container = None
        self._up_source = None

        self._log_html_engine = None
        self._log_html_sched = None

        self._ops_dialog = None
        self._ops_html = None
        self._ops_busy = False

        self._btn_down = None
        self._btn_up = None
        self._btn_recreate = None
        self._btn_update = None

        self._tag_select = None
        self._tag_value = None  # type: ignore[assignment]

        self._restart_badge = None

        self._tabs = None
        self._tab_dashboard = "Dashboard"
        self._tab_settings = "Settings"

        self._settings_service = "engine"
        self._settings_advanced = False
        self._settings_service_select = None
        self._settings_advanced_switch = None
        self._settings_search = None
        self._settings_grid_container = None
        self._settings_env_base: Dict[str, str] = {}
        self._settings_env_work: Dict[str, str] = {}
        self._settings_inputs: Dict[str, Any] = {}

        self._settings_topcat_container = None
        self._settings_topcat_tabs = None
        self._settings_topcat_value: Optional[str] = None

        self._settings_show_unmapped = False
        self._settings_show_unmapped_switch = None

        self._topcats_order: List[str] = []

        self._env_ref_by_key: Dict[str, Dict[str, str]] = {}
        self._category_order: List[str] = []

        self._compose_env_busy = False
        self._compose_env_format = "dict"

        self._load_env_reference_csv()

    # -------------------- Small helpers --------------------

    def _stream_public_url(self) -> str:
        public = getattr(self.settings, "icecast_public_url", "") or ""
        public = str(public).strip()
        if public:
            return public.rstrip("/")

        scheme = getattr(self.settings, "icecast_scheme", "http")
        host = getattr(self.settings, "icecast_host", "localhost")
        port = getattr(self.settings, "icecast_port", 8000)
        mount = getattr(self.settings, "icecast_mount", "/")
        if not str(mount).startswith("/"):
            mount = "/" + str(mount)
        return f"{scheme}://{host}:{port}{mount}"

    def _default_tag_from_image(self) -> str:
        s = (self.settings.azursmartmix_image or "").strip()
        if ":" in s:
            return s.rsplit(":", 1)[1].strip() or "latest"
        return "latest"

    def _compose_env_endpoint(self, service: str) -> str:
        if service == "scheduler":
            return "/compose/scheduler_env"
        return "/compose/engine_env"

    def _key_is_bool_flag(self, key: str) -> bool:
        if not key:
            return False
        u = str(key).strip().upper()
        if not u:
            return False
        if u.endswith(self._BOOL_KEY_SUFFIXES):
            return True
        for frag in self._BOOL_KEY_CONTAINS:
            if frag in u:
                return True
        if u in {"LS_CHECK", "SCHED_ACCESS_LOG", "SCHED_ACCESSLOG"}:
            return True
        if u.startswith("LOG_"):
            return True
        return False

    def _parse_bool_like_key(self, key: str, v: Any) -> Optional[bool]:
        if v is None:
            return None
        s = str(v).strip().lower()
        if s in self._BOOL_TRUE_WORD:
            return True
        if s in self._BOOL_FALSE_WORD:
            return False
        if s in self._BOOL_NUM:
            if self._key_is_bool_flag(key):
                return True if s == "1" else False
            return None
        return None

    def _format_bool_like(self, template_val: Any, b: bool) -> str:
        t = "" if template_val is None else str(template_val).strip().lower()
        if t in {"0", "1"}:
            return "1" if b else "0"
        if t in {"on", "off"}:
            return "on" if b else "off"
        if t in {"yes", "no", "y", "n"}:
            return "yes" if b else "no"
        if t in {"enabled", "disabled"}:
            return "enabled" if b else "disabled"
        return "true" if b else "false"

    def _is_number_like(self, v: Any) -> bool:
        if v is None:
            return False
        s = str(v).strip()
        if not s:
            return False
        try:
            float(s)
            return True
        except Exception:
            return False

    def build(self) -> None:
        ui.add_head_html(f"<style>{AZURA_CSS}</style>")
        ui.add_head_html(f"<script>{AZURA_JS}</script>")
        ui.page_title("AzurSmartMix Control")

        self._build_ops_dialog()

        with ui.header().classes("az-topbar items-center justify-between"):
            with ui.row().classes("items-center gap-3"):
                ui.label("azuracast").classes("az-brand text-xl")
                ui.label("AzurSmartMix Control").classes("az-sub text-sm")
                self._restart_badge = ui.html("").classes("ml-2")

            with ui.row().classes("items-center gap-2 az-opbtn"):
                default_tag = self._default_tag_from_image()
                self._tag_value = default_tag

                self._tag_select = ui.select(
                    options=["latest", "beta1", "beta2", "rc", "dev"],
                    value=default_tag,
                    label="Tag",
                    on_change=self._on_tag_change,
                ).props("dense outlined dark").style("min-width: 140px;")

                self._btn_up = ui.button("Start", on_click=self.op_compose_up).props(
                    "unelevated color=positive"
                )
                self._btn_down = ui.button("Stop", on_click=self.op_compose_down).props(
                    "unelevated color=negative"
                )
                self._btn_recreate = ui.button(
                    "Recreate", on_click=self.op_compose_recreate
                ).props("unelevated color=warning")
                self._btn_update = ui.button("Update", on_click=self.op_compose_update).props(
                    "outline"
                )

                ui.separator().props("vertical").style("height:26px; opacity:.35;")

                ui.button("Refresh", on_click=self.refresh_visible).props(
                    "unelevated color=white text-color=primary"
                )
                ui.button("Auto 5s", on_click=self.enable_autorefresh).props("outline")
                ui.button("Stop Auto", on_click=self.disable_autorefresh).props("outline")

        with ui.element("div").classes("az-wrap"):
            with ui.element("div").classes("az-tabsbar"):
                with ui.tabs(value=self._tab_dashboard, on_change=self._on_main_tab_change).classes(
                    "w-full"
                ) as self._tabs:
                    ui.tab(self._tab_dashboard)
                    ui.tab(self._tab_settings)

            with ui.tab_panels(self._tabs, value=self._tab_dashboard).classes("w-full"):
                with ui.tab_panel(self._tab_dashboard):
                    with ui.element("div").classes("az-grid-3"):
                        self._card_resources()
                        self._card_runtime()
                    with ui.element("div").classes("az-grid").style("margin-top: 16px;"):
                        self._card_now()
                        self._card_upcoming()
                    with ui.element("div").classes("az-grid").style("margin-top: 16px;"):
                        self._card_logs()

                with ui.tab_panel(self._tab_settings):
                    self._card_settings()

        ui.timer(0.1, self.refresh_dashboard, once=True)
        ui.timer(0.2, self.refresh_settings, once=True)

    def _current_main_tab(self) -> str:
        try:
            value = getattr(self._tabs, "value", None)
            if value is not None:
                s = str(value).strip()
                if s:
                    return s
        except Exception:
            pass
        return self._tab_dashboard

    async def _on_main_tab_change(self, e) -> None:
        try:
            value = str(e.value).strip() if e.value is not None else self._tab_dashboard
        except Exception:
            value = self._tab_dashboard

        if value == self._tab_settings:
            await self.refresh_settings()
            return
        await self.refresh_dashboard()

    async def refresh_visible(self) -> None:
        if self._current_main_tab() == self._tab_settings:
            await self.refresh_settings()
            return
        await self.refresh_dashboard()

    def _on_tag_change(self, e) -> None:
        try:
            self._tag_value = str(e.value).strip()
        except Exception:
            self._tag_value = self._default_tag_from_image()

    def _set_restart_needed(self, needed: bool) -> None:
        if not self._restart_badge:
            return
        if not bool(needed):
            self._restart_badge.set_content("")
            return
        self._restart_badge.set_content(
            '<span class="az-badge" style="border-color: rgba(245,158,11,.55); background: rgba(245,158,11,.15);">'
            '<span class="az-dot warn"></span>'
            "<span>Need restart to take effect</span>"
            "</span>"
        )

    # -------------------- Ops modal + API calls --------------------

    def _build_ops_dialog(self) -> None:
        with ui.dialog() as d:
            self._ops_dialog = d
            with ui.card().classes("az-card").style("min-width: 920px; max-width: 1200px;"):
                with ui.element("div").classes("az-card-h"):
                    ui.label("Operations Console")
                    ui.button("Close", on_click=d.close).props("outline")
                with ui.element("div").classes("az-card-b"):
                    ui.label(f"cwd: {self.settings.azuramix_dir}").style(
                        "font-family: var(--az-mono); font-size: 13px; opacity:.85;"
                    )
                    ui.label(f"compose: {self.settings.azuramix_compose_file}").style(
                        "font-family: var(--az-mono); font-size: 13px; opacity:.65; margin-top: 2px;"
                    )
                    ui.separator().style("opacity:.25; margin: 10px 0;")
                    with ui.element("div").classes("console-frame").style("height: 520px;"):
                        self._ops_html = ui.html('<div class="console-content">—</div>')

    async def _post_text(self, path: str) -> str:
        url = f"http://127.0.0.1:{self.settings.ui_port}{self.api_base}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(url)
            r.raise_for_status()
            return r.text

    async def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"http://127.0.0.1:{self.settings.ui_port}{self.api_base}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, dict) else {"data": data}

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

    def _set_ops_busy(self, busy: bool) -> None:
        self._ops_busy = bool(busy)
        for b in (self._btn_down, self._btn_up, self._btn_recreate, self._btn_update):
            if b:
                b.disable() if busy else b.enable()
        if self._tag_select:
            self._tag_select.disable() if busy else self._tag_select.enable()

    async def _run_op(self, label: str, path: str, clears_restart_hint: bool = False) -> None:
        if self._ops_busy:
            ui.notify("Operation already running", type="warning")
            return

        self._set_ops_busy(True)
        try:
            if self._ops_dialog:
                self._ops_dialog.open()
            if self._ops_html:
                self._ops_html.set_content(
                    f'<div class="console-content">{html.escape(f"== {label} ==\\nPOST {path}\\n\\nrunning...\\n")}</div>'
                )

            txt = await self._post_text(path)

            if self._ops_html:
                self._ops_html.set_content(f'<div class="console-content">{html.escape(txt)}</div>')

            ui.notify(f"{label}: done", type="positive")
            if clears_restart_hint:
                self._set_restart_needed(False)

            await self.refresh_dashboard()
        except Exception as e:
            if self._ops_html:
                self._ops_html.set_content(
                    f'<div class="console-content">{html.escape(f"== {label} ==\\nerror: {e}\\n")}</div>'
                )
            ui.notify(f"{label}: error", type="negative")
        finally:
            self._set_ops_busy(False)

    async def op_compose_down(self) -> None:
        await self._run_op(
            "Stop (docker compose down)",
            "/ops/compose/down",
            clears_restart_hint=False,
        )

    async def op_compose_up(self) -> None:
        await self._run_op(
            "Start (docker compose up -d)",
            "/ops/compose/up",
            clears_restart_hint=True,
        )

    async def op_compose_recreate(self) -> None:
        await self._run_op(
            "Recreate (up -d --force-recreate)",
            "/ops/compose/recreate",
            clears_restart_hint=True,
        )

    async def op_compose_update(self) -> None:
        tag = str(self._tag_value or "").strip()
        qs = ""
        if tag:
            qs = "?tag=" + urllib.parse.quote(tag, safe="")
        await self._run_op(
            f"Update (down + rm image:{tag or 'default'})",
            "/ops/compose/update" + qs,
            clears_restart_hint=True,
        )

    async def _autorefresh_tick(self) -> None:
        if self._current_main_tab() != self._tab_dashboard:
            return
        await self.refresh_dashboard()

    def enable_autorefresh(self) -> None:
        if self._timer is not None:
            return
        self._timer = ui.timer(5.0, self._autorefresh_tick)

    def disable_autorefresh(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._timer = None
