from __future__ import annotations

from typing import Any, Dict, List

import httpx
from nicegui import ui

from azursmartmix_control.config import Settings


AZURA_CSS = r"""
:root{
  --az-blue: #1e88e5;
  --az-blue-dark: #1565c0;
  --az-bg: #1f242d;
  --az-bg2: #262c37;
  --az-card: #262c37;
  --az-card2: #2b3340;
  --az-border: rgba(255,255,255,.08);
  --az-text: rgba(255,255,255,.92);
  --az-muted: rgba(255,255,255,.65);
  --az-muted2: rgba(255,255,255,.45);
  --az-green: #22c55e;
  --az-orange: #f59e0b;
  --az-red: #ef4444;
  --az-shadow: 0 10px 30px rgba(0,0,0,.25);
  --az-radius: 10px;
  --az-font: Inter, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Arial, sans-serif;
  --az-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

html, body {
  background: var(--az-bg) !important;
  color: var(--az-text) !important;
  font-family: var(--az-font) !important;
}

/* Remove default nicegui spacing quirks */
.q-page-container, .q-layout, .q-page { background: var(--az-bg) !important; }

/* Topbar */
.az-topbar {
  background: linear-gradient(0deg, var(--az-blue) 0%, var(--az-blue-dark) 100%) !important;
  color: white !important;
  border-bottom: 1px solid rgba(255,255,255,.15);
  box-shadow: var(--az-shadow);
}
.az-topbar .az-brand {
  font-weight: 800;
  letter-spacing: .2px;
}
.az-topbar .az-sub {
  opacity: .85;
  font-weight: 500;
}

/* Main container */
.az-wrap {
  width: 100%;
  max-width: 1240px;
  margin: 0 auto;
  padding: 18px 18px 28px 18px;
}

/* Grid 2 columns */
.az-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
@media (max-width: 1100px){
  .az-grid { grid-template-columns: 1fr; }
}

/* Cards */
.az-card {
  background: var(--az-card) !important;
  border: 1px solid var(--az-border);
  border-radius: var(--az-radius);
  box-shadow: var(--az-shadow);
  overflow: hidden;
}
.az-card-h {
  background: var(--az-blue) !important;
  color: white !important;
  padding: 12px 14px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.az-card-b {
  padding: 14px;
  background: linear-gradient(180deg, var(--az-card2), var(--az-card));
}

/* Mini badges */
.az-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 999px;
  font-weight: 700;
  font-size: 12px;
  border: 1px solid var(--az-border);
  background: rgba(255,255,255,.05);
}
.az-dot { width: 10px; height: 10px; border-radius: 999px; display: inline-block; }
.az-dot.ok { background: var(--az-green); }
.az-dot.warn { background: var(--az-orange); }
.az-dot.err { background: var(--az-red); }

.az-kv {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 10px 14px;
  font-size: 13px;
  line-height: 1.45;
}
.az-kv .k { color: var(--az-muted); }
.az-kv .v { color: var(--az-text); word-break: break-word; }
.az-mono { font-family: var(--az-mono); }

.az-now-title {
  font-size: 20px;
  font-weight: 900;
  margin: 2px 0 6px 0;
}
.az-small { color: var(--az-muted); font-size: 12px; }

.az-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.az-item {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--az-border);
  background: rgba(255,255,255,.04);
}
.az-item .idx {
  display: inline-block;
  min-width: 24px;
  font-weight: 900;
  color: rgba(255,255,255,.75);
}
.az-item .txt {
  font-weight: 600;
}

.az-actions .q-btn {
  border-radius: 10px !important;
  font-weight: 800 !important;
  text-transform: none !important;
}
.az-actions .q-btn--outline {
  border: 1px solid rgba(255,255,255,.55) !important;
  color: white !important;
}

.az-tabs .q-tab { color: rgba(255,255,255,.75) !important; }
.az-tabs .q-tab--active { color: white !important; font-weight: 900 !important; }
.az-tabs .q-tab-panels { background: transparent !important; }

.az-textarea textarea {
  font-family: var(--az-mono) !important;
  font-size: 12px !important;
  color: rgba(255,255,255,.90) !important;
  background: rgba(0,0,0,.25) !important;
}

.az-table .q-table__container {
  background: rgba(0,0,0,.15) !important;
  border: 1px solid var(--az-border) !important;
  border-radius: 10px !important;
}
.az-table thead tr th {
  color: rgba(255,255,255,.80) !important;
}
.az-table tbody tr td {
  color: rgba(255,255,255,.90) !important;
}
"""

AZURA_JS = r"""
// Tiny helper: allow click-to-copy on any element with data-copy.
document.addEventListener('click', (ev) => {
  const el = ev.target.closest('[data-copy]');
  if (!el) return;
  const txt = el.getAttribute('data-copy') || el.textContent || '';
  if (!txt) return;
  navigator.clipboard.writeText(txt).then(() => {
    el.classList.add('copied');
    setTimeout(() => el.classList.remove('copied'), 400);
  }).catch(()=>{});
});
"""


class ControlUI:
    """AzurCast-ish control panel (2 columns) with CSS+JS supercharge."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_base = settings.api_prefix.rstrip("/")
        self.timeout = httpx.Timeout(2.5, connect=1.5)
        self._timer = None

        # runtime
        self._docker_badge = None
        self._engine_kv = {}
        self._sched_kv = {}

        # now/upcoming
        self._now_title = None
        self._up_list_container = None

        # env
        self._env_table = None

        # logs
        self._logs_engine = None
        self._logs_sched = None

    def build(self) -> None:
        ui.add_head_html(f"<style>{AZURA_CSS}</style>")
        ui.add_head_html(f"<script>{AZURA_JS}</script>")

        ui.page_title("AzurSmartMix Control")

        # Topbar
        with ui.header().classes("az-topbar items-center justify-between"):
            with ui.row().classes("items-center gap-3"):
                ui.label("azuracast").classes("az-brand text-xl")
                ui.label("AzurSmartMix Control").classes("az-sub text-sm")
            with ui.row().classes("items-center gap-2 az-actions"):
                ui.button("Refresh", on_click=self.refresh_all).props("unelevated color=white text-color=primary")
                ui.button("Auto 5s", on_click=self.enable_autorefresh).props("outline")
                ui.button("Stop", on_click=self.disable_autorefresh).props("outline")

        # Main wrap + grid
        with ui.element("div").classes("az-wrap"):
            with ui.element("div").classes("az-grid"):
                # LEFT COL
                self._card_runtime()
                self._card_env()

                # RIGHT COL
                self._card_now()
                self._card_upcoming()

            # Full width logs below (2 columns)
            with ui.element("div").classes("az-grid").style("margin-top: 16px;"):
                self._card_logs()

        ui.timer(0.1, self.refresh_all, once=True)

    # -------- Cards --------

    def _card_runtime(self) -> None:
        with ui.element("div").classes("az-card"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Runtime Status")
                self._docker_badge = ui.html(
                    '<span class="az-badge"><span class="az-dot warn"></span><span>Docker: …</span></span>'
                )
            with ui.element("div").classes("az-card-b"):
                with ui.row().classes("w-full gap-4"):
                    self._engine_kv = self._kv_block("Engine")
                    self._sched_kv = self._kv_block("Scheduler")

    def _kv_block(self, title: str) -> Dict[str, Any]:
        with ui.element("div").style("flex:1; min-width: 280px;"):
            ui.label(title).classes("text-sm font-bold").style("margin-bottom: 10px; opacity:.9;")
            kv = ui.element("div").classes("az-kv")
            rows = {
                "name": ui.html(""),
                "image": ui.html(""),
                "status": ui.html(""),
                "health": ui.html(""),
                "uptime": ui.html(""),
            }
            # init placeholders
            with kv:
                self._kv_row("name", rows["name"])
                self._kv_row("image", rows["image"], mono=True)
                self._kv_row("status", rows["status"])
                self._kv_row("health", rows["health"])
                self._kv_row("uptime", rows["uptime"])
            return rows

    def _kv_row(self, key: str, value_widget: Any, mono: bool = False) -> None:
        ui.html(f'<div class="k">{key}</div>')
        cls = "v az-mono" if mono else "v"
        # data-copy enables click-to-copy via AZURA_JS
        value_widget.set_content(f'<div class="{cls}" data-copy="">—</div>')

    def _card_env(self) -> None:
        with ui.element("div").classes("az-card"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Engine env (docker-compose)")
                ui.label(self.settings.compose_service_engine).classes("text-xs").style("opacity:.85;")
            with ui.element("div").classes("az-card-b"):
                self._env_table = ui.table(
                    columns=[
                        {"name": "key", "label": "KEY", "field": "key", "align": "left"},
                        {"name": "value", "label": "VALUE", "field": "value", "align": "left"},
                    ],
                    rows=[],
                    row_key="key",
                ).classes("w-full az-table")
                self._env_table.props("dense flat")

    def _card_now(self) -> None:
        with ui.element("div").classes("az-card"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Now Playing")
                ui.label(self.settings.icecast_mount).classes("text-xs").style("opacity:.85;")
            with ui.element("div").classes("az-card-b"):
                self._now_title = ui.label("—").classes("az-now-title")
                ui.label("Icecast metadata (title only)").classes("az-small")

    def _card_upcoming(self) -> None:
        with ui.element("div").classes("az-card"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Upcoming")
                ui.label("from engine preprocess log").classes("text-xs").style("opacity:.85;")
            with ui.element("div").classes("az-card-b"):
                self._up_list_container = ui.element("div").classes("az-list")

    def _card_logs(self) -> None:
        with ui.element("div").classes("az-card").style("grid-column: 1 / -1;"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Logs")
                ui.label("tail=200").classes("text-xs").style("opacity:.85;")
            with ui.element("div").classes("az-card-b az-tabs"):
                tabs = ui.tabs().classes("w-full")
                t_engine = ui.tab("engine")
                t_sched = ui.tab("scheduler")

                with ui.tab_panels(tabs, value=t_engine).classes("w-full"):
                    with ui.tab_panel(t_engine):
                        self._logs_engine = ui.textarea(value="").props("readonly rows=16").classes("w-full az-textarea")
                    with ui.tab_panel(t_sched):
                        self._logs_sched = ui.textarea(value="").props("readonly rows=16").classes("w-full az-textarea")

    # -------- HTTP helpers --------

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

    # -------- Refresh cycle --------

    async def refresh_all(self) -> None:
        await self.refresh_runtime()
        await self.refresh_engine_env()
        await self.refresh_now()
        await self.refresh_upcoming()
        await self.refresh_logs()

    async def refresh_runtime(self) -> None:
        try:
            rt = await self._get_json("/panel/runtime")
        except Exception as e:
            self._set_docker_badge(ok=False, text=f"Docker: error")
            return

        docker_ok = bool(rt.get("docker_ping"))
        self._set_docker_badge(ok=docker_ok, text=f"Docker: {'OK' if docker_ok else 'DOWN'}")

        self._fill_kv(self._engine_kv, rt.get("engine") or {})
        self._fill_kv(self._sched_kv, rt.get("scheduler") or {})

    def _set_docker_badge(self, ok: bool, text: str) -> None:
        if self._docker_badge is None:
            return
        dot = "ok" if ok else "err"
        self._docker_badge.set_content(f'<span class="az-badge"><span class="az-dot {dot}"></span><span>{text}</span></span>')

    def _fill_kv(self, kv: Dict[str, Any], data: Dict[str, Any]) -> None:
        if not kv:
            return
        if not data.get("present"):
            self._set_kv_value(kv["name"], data.get("name") or "missing")
            self._set_kv_value(kv["image"], "-")
            self._set_kv_value(kv["status"], "missing")
            self._set_kv_value(kv["health"], "-")
            self._set_kv_value(kv["uptime"], "-")
            return

        self._set_kv_value(kv["name"], data.get("name") or "—")
        self._set_kv_value(kv["image"], data.get("image") or "—")
        self._set_kv_value(kv["status"], data.get("status") or "—")
        self._set_kv_value(kv["health"], data.get("health") or "-")
        self._set_kv_value(kv["uptime"], data.get("uptime") or "-")

    def _set_kv_value(self, widget: Any, value: str) -> None:
        safe = (value or "—").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        widget.set_content(f'<div class="v" data-copy="{safe}">{safe}</div>')

    async def refresh_engine_env(self) -> None:
        if self._env_table is None:
            return
        try:
            data = await self._get_json("/panel/engine_env")
            env = data.get("environment") if isinstance(data, dict) else None
            if not isinstance(env, dict):
                rows = [{"key": "error", "value": str(data)}]
            else:
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
            self._now_title.set_text("—")

    async def refresh_upcoming(self) -> None:
        if self._up_list_container is None:
            return
        try:
            up = await self._get_json("/panel/upcoming?n=10")
            titles = up.get("upcoming") or []
            if not isinstance(titles, list):
                titles = []
        except Exception:
            titles = []

        self._up_list_container.clear()
        with self._up_list_container:
            if not titles:
                ui.html('<div class="az-small">—</div>')
                return
            for i, t in enumerate(titles, start=1):
                t_safe = str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                ui.html(f'<div class="az-item"><span class="idx">{i}.</span> <span class="txt" data-copy="{t_safe}">{t_safe}</span></div>')

    async def refresh_logs(self) -> None:
        try:
            eng = await self._get_text("/logs?service=engine&tail=200")
            if self._logs_engine:
                self._logs_engine.set_value(eng)
        except Exception:
            if self._logs_engine:
                self._logs_engine.set_value("")

        try:
            sch = await self._get_text("/logs?service=scheduler&tail=200")
            if self._logs_sched:
                self._logs_sched.set_value(sch)
        except Exception:
            if self._logs_sched:
                self._logs_sched.set_value("")

    def enable_autorefresh(self) -> None:
        if self._timer is not None:
            return
        self._timer = ui.timer(5.0, self.refresh_all)

    def disable_autorefresh(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._timer = None
