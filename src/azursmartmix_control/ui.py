from __future__ import annotations

from typing import Any, Dict, List, Tuple

import html
import re

import httpx
from nicegui import ui

from azursmartmix_control.config import Settings


AZURA_CSS = r"""
:root{
  --az-blue: #1e88e5;
  --az-blue-dark: #1565c0;
  --az-bg: #1f242d;
  --az-card: #262c37;
  --az-card2: #2b3340;
  --az-border: rgba(255,255,255,.08);
  --az-text: rgba(255,255,255,.92);
  --az-muted: rgba(255,255,255,.65);
  --az-green: #22c55e;
  --az-red: #ef4444;
  --az-orange: #f59e0b;
  --az-cyan: #22d3ee;
  --az-violet: #a78bfa;
  --az-shadow: 0 10px 30px rgba(0,0,0,.25);
  --az-radius: 10px;
  --az-font: Inter, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Arial, sans-serif;
  --az-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  --wrap-max: 1860px;
  --grid-gap: 18px;
}

/* Global: never allow light backgrounds to leak */
html, body { background: var(--az-bg) !important; color: var(--az-text) !important; font-family: var(--az-font) !important; }
.q-page-container, .q-layout, .q-page { background: var(--az-bg) !important; }
.q-card, .q-table__container, .q-menu, .q-dialog__inner, .q-drawer { background: transparent !important; }

/* Nuke Quasar panel/tabs backgrounds */
.q-tab-panels,
.q-tab-panel,
.q-panel,
.q-panel-parent,
.q-tabs,
.q-tabs__content,
.q-tab-panels .q-panel,
.q-tab-panels .q-panel-parent {
  background: transparent !important;
}

/* Some NiceGUI HTML wrapper can have background */
.q-html,
.q-html * {
  background: transparent !important;
}

.az-topbar{
  background: linear-gradient(0deg, var(--az-blue) 0%, var(--az-blue-dark) 100%) !important;
  color: white !important;
  border-bottom: 1px solid rgba(255,255,255,.15);
  box-shadow: var(--az-shadow);
}
.az-topbar .az-brand { font-weight: 900; }
.az-topbar .az-sub { opacity: .85; font-weight: 600; }

.az-wrap{ width:100%; max-width: var(--wrap-max); margin: 0 auto; padding: 18px 18px 28px 18px; }
.az-grid{ display:grid; grid-template-columns: 1fr 1fr; gap: var(--grid-gap); }
@media (max-width: 1200px){ .az-grid{ grid-template-columns: 1fr; } }

.az-card{
  background: var(--az-card) !important;
  border: 1px solid var(--az-border);
  border-radius: var(--az-radius);
  box-shadow: var(--az-shadow);
  overflow: hidden;
  min-width: 520px;
}
@media (max-width: 1200px){ .az-card{ min-width: unset; } }

.az-card-h{
  background: var(--az-blue) !important;
  color: white !important;
  padding: 12px 14px;
  font-weight: 900;
  display:flex; align-items:center; justify-content:space-between;
}
.az-card-b{ padding: 14px; background: linear-gradient(180deg, var(--az-card2), var(--az-card)); }

.az-badge{
  display:inline-flex; align-items:center; gap:8px;
  padding:6px 10px; border-radius:999px;
  font-weight:900; font-size:12px;
  border:1px solid var(--az-border);
  background: rgba(255,255,255,.05);
}
.az-dot{ width:10px; height:10px; border-radius:999px; display:inline-block; }
.az-dot.ok{ background: var(--az-green); }
.az-dot.err{ background: var(--az-red); }
.az-dot.warn{ background: var(--az-orange); }

.az-actions .q-btn{ border-radius: 10px !important; font-weight: 900 !important; text-transform:none !important; }
.az-actions .q-btn--outline{ border:1px solid rgba(255,255,255,.55) !important; color:white !important; }

.az-list{ display:flex; flex-direction:column; gap:8px; }
.az-item{ padding: 10px 12px; border-radius: 10px; border: 1px solid var(--az-border); background: rgba(255,255,255,.04); }
.az-item .idx{ display:inline-block; min-width:24px; font-weight:950; color: rgba(255,255,255,.75); }
.az-item .txt{ font-weight:650; }

/* ===== Runtime tables ===== */
.rt-grid{ display:grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 900px){ .rt-grid{ grid-template-columns: 1fr; } }

.rt-box{
  border: 1px solid var(--az-border);
  border-radius: 10px;
  background: rgba(0,0,0,.10);
  overflow: hidden;
}
.rt-box-h{
  padding: 10px 12px;
  font-weight: 900;
  border-bottom: 1px solid rgba(255,255,255,.08);
  color: rgba(255,255,255,.92);
}
.rt-table{ width: 100%; border-collapse: collapse; font-size: 13px; }
.rt-table tr td{
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255,255,255,.06);
  vertical-align: top;
}
.rt-table tr:last-child td{ border-bottom: none; }
.rt-k{ width: 140px; color: var(--az-muted); }
.rt-v{ color: rgba(255,255,255,.92); font-family: var(--az-mono); word-break: break-word; }

/* ===== Engine env viewer ===== */
.env-toolbar{ display:flex; gap:10px; align-items:center; margin-bottom: 10px; }
.env-search input{ font-family: var(--az-mono) !important; }
.env-frame{
  max-height: 360px;
  overflow-y: auto;
  padding-right: 6px;
  border: 1px solid var(--az-border);
  border-radius: 10px;
  background: rgba(0,0,0,.12);
}
.env-row{
  display:grid;
  grid-template-columns: 260px 1fr;
  gap: 10px;
  padding: 8px 10px;
  border-bottom: 1px solid rgba(255,255,255,.06);
}
.env-row:last-child{ border-bottom: none; }
.env-k{
  font-family: var(--az-mono);
  font-size: 12px;
  color: rgba(255,255,255,.80);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.env-v{
  font-family: var(--az-mono);
  font-size: 12px;
  color: rgba(255,255,255,.92);
  word-break: break-word;
}
.env-row:hover{ background: rgba(255,255,255,.05); }

.env-frame::-webkit-scrollbar{ width: 10px; }
.env-frame::-webkit-scrollbar-track{ background: rgba(255,255,255,.06); border-radius: 10px; }
.env-frame::-webkit-scrollbar-thumb{ background: rgba(255,255,255,.22); border-radius: 10px; }
.env-frame::-webkit-scrollbar-thumb:hover{ background: rgba(255,255,255,.34); }

/* ===== Console viewer ===== */
.console-frame{
  height: 420px;
  overflow: auto;
  border: 1px solid var(--az-border);
  border-radius: 10px;
  background: rgba(0,0,0,.55) !important;
  padding: 10px 12px;
}
.console-frame, .console-frame * { background: transparent !important; }
.console-frame { background: rgba(0,0,0,.55) !important; }
.console-content{
  font-family: var(--az-mono) !important;
  font-size: 12px !important;
  line-height: 1.35 !important;
  color: rgba(255,255,255,.86) !important;
  white-space: pre-wrap !important;
  word-break: break-word !important;
  margin: 0 !important;
  padding: 0 !important;
}

/* tokens */
.t-dim{ color: rgba(255,255,255,.45) !important; }
.t-info{ color: rgba(56, 189, 248, .95) !important; }
.t-warn{ color: rgba(245, 158, 11, .95) !important; }
.t-err{  color: rgba(239, 68, 68, .95) !important; }
.t-ok{   color: rgba(34, 197, 94, .95) !important; }
.t-vio{  color: rgba(167, 139, 250, .95) !important; }
.t-cyan{ color: rgba(34, 211, 238, .95) !important; }
.t-bold{ font-weight: 900 !important; }

/* ===== HTML5 audio player ===== */
.az-player{
  width: 100%;
  margin-top: 10px;
  padding: 10px 10px;
  border-radius: 12px;
  border: 1px solid var(--az-border);
  background: rgba(0,0,0,.22);
}
.az-player audio{
  width: 100%;
  height: 42px;
  filter: invert(1) hue-rotate(180deg) saturate(1.2); /* make native controls "dark-ish" */
  opacity: 0.95;
}
.az-player .hint{
  margin-top: 8px;
  font-size: 12px;
  color: rgba(255,255,255,.65);
  font-family: var(--az-mono);
}
"""

AZURA_JS = r"""
document.addEventListener('click', (ev) => {
  const el = ev.target.closest('[data-copy]');
  if (!el) return;
  const txt = el.getAttribute('data-copy') || el.textContent || '';
  if (!txt) return;
  navigator.clipboard.writeText(txt).catch(()=>{});
});
"""


class ControlUI:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_base = settings.api_prefix.rstrip("/")
        self.timeout = httpx.Timeout(2.5, connect=1.5)
        self._timer = None

        self._docker_badge = None
        self._rt_engine_tbl = None
        self._rt_sched_tbl = None

        self._now_title = None
        self._now_player = None

        self._up_list_container = None

        self._env_search = None
        self._env_frame = None
        self._env_rows: List[Tuple[str, str]] = []

        self._log_html_engine = None
        self._log_html_sched = None

    def _stream_public_url(self) -> str:
        # Prefer explicit env var if present in Settings (backward-compatible if not)
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

    def build(self) -> None:
        ui.add_head_html(f"<style>{AZURA_CSS}</style>")
        ui.add_head_html(f"<script>{AZURA_JS}</script>")
        ui.page_title("AzurSmartMix Control")

        with ui.header().classes("az-topbar items-center justify-between"):
            with ui.row().classes("items-center gap-3"):
                ui.label("azuracast").classes("az-brand text-xl")
                ui.label("AzurSmartMix Control").classes("az-sub text-sm")
            with ui.row().classes("items-center gap-2 az-actions"):
                ui.button("Refresh", on_click=self.refresh_all).props("unelevated color=white text-color=primary")
                ui.button("Auto 5s", on_click=self.enable_autorefresh).props("outline")
                ui.button("Stop", on_click=self.disable_autorefresh).props("outline")

        with ui.element("div").classes("az-wrap"):
            with ui.element("div").classes("az-grid"):
                self._card_runtime()
                self._card_env()
                self._card_now()
                self._card_upcoming()

            with ui.element("div").classes("az-grid").style("margin-top: 16px;"):
                self._card_logs()

        ui.timer(0.1, self.refresh_all, once=True)

    # ---------- Cards ----------

    def _card_runtime(self) -> None:
        with ui.element("div").classes("az-card"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Runtime Status")
                self._docker_badge = ui.html(
                    '<span class="az-badge"><span class="az-dot warn"></span><span>Docker: …</span></span>'
                )
            with ui.element("div").classes("az-card-b"):
                with ui.element("div").classes("rt-grid"):
                    self._rt_engine_tbl = self._runtime_box("Engine")
                    self._rt_sched_tbl = self._runtime_box("Scheduler")

    def _runtime_box(self, title: str):
        with ui.element("div").classes("rt-box"):
            ui.label(title).classes("rt-box-h")
            tbl = ui.html(self._runtime_table_html({}))
            return tbl

    def _runtime_table_html(self, data: Dict[str, Any]) -> str:
        def v(key: str, default: str = "—") -> str:
            raw = data.get(key)
            if raw is None or raw == "":
                raw = default
            return html.escape(str(raw))

        rows = [
            ("name", v("name")),
            ("image", v("image")),
            ("status", v("status")),
            ("health", v("health", "-")),
            ("uptime", v("uptime", "-")),
        ]
        tr = "".join(
            f'<tr><td class="rt-k">{html.escape(k)}</td><td class="rt-v" data-copy="{val}">{val}</td></tr>'
            for k, val in rows
        )
        return f'<table class="rt-table">{tr}</table>'

    def _card_env(self) -> None:
        with ui.element("div").classes("az-card"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Engine env (docker-compose)")
                ui.label(self.settings.compose_service_engine).classes("text-xs").style("opacity:.85;")
            with ui.element("div").classes("az-card-b"):
                with ui.element("div").classes("env-toolbar"):
                    self._env_search = ui.input(placeholder="Filter (key/value)…").classes("env-search").props("dense outlined")
                    ui.button("Clear", on_click=self._env_clear_filter).props("outline")
                self._env_frame = ui.element("div").classes("env-frame")

    def _card_now(self) -> None:
        stream_url = self._stream_public_url()
        mount = getattr(self.settings, "icecast_mount", "/gst-test.mp3")
        with ui.element("div").classes("az-card"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Now Playing")
                ui.label(str(mount)).classes("text-xs").style("opacity:.85;")
            with ui.element("div").classes("az-card-b"):
                self._now_title = ui.label("—").classes("text-xl").style("font-weight: 950; margin: 2px 0 0 0;")

                # HTML5 player
                self._now_player = ui.html(self._player_html(stream_url))

                ui.label("Icecast metadata (title only)").style("font-size: 12px; opacity:.7; margin-top: 10px;")

    def _player_html(self, url: str) -> str:
        u = html.escape(url)
        return (
            f'<div class="az-player">'
            f'  <audio controls preload="none" crossorigin="anonymous">'
            f'    <source src="{u}" type="audio/mpeg" />'
            f'  </audio>'
            f'  <div class="hint" data-copy="{u}">{u}</div>'
            f'</div>'
        )

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
            with ui.element("div").classes("az-card-b"):
                tabs = ui.tabs().classes("w-full")
                t_engine = ui.tab("engine")
                t_sched = ui.tab("scheduler")

                with ui.tab_panels(tabs, value=t_engine).classes("w-full"):
                    with ui.tab_panel(t_engine):
                        with ui.element("div").classes("console-frame").style("background: rgba(0,0,0,.55) !important;"):
                            self._log_html_engine = ui.html('<div class="console-content">—</div>')
                    with ui.tab_panel(t_sched):
                        with ui.element("div").classes("console-frame").style("background: rgba(0,0,0,.55) !important;"):
                            self._log_html_sched = ui.html('<div class="console-content">—</div>')

    # ---------- HTTP helpers ----------

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

    # ---------- Log highlight ----------

    _re_level = re.compile(r"\b(INFO|WARN|WARNING|ERROR|CRITICAL|DEBUG)\b")
    _re_engine_tag = re.compile(r"\bazurmixd\.engine\b")
    _re_sched_tag = re.compile(r"\bazurmixd\.scheduler\b")
    _re_preprocess = re.compile(r"\bpreprocess:\b")
    _re_bridge = re.compile(r"\bbridgeplan:\b")
    _re_aft = re.compile(r"\bAFT#\d+\b")
    _re_icecast = re.compile(r"\b(Icecast|ICECAST|/status-json\.xsl|mount|listeners?)\b", re.IGNORECASE)
    _re_uri = re.compile(r"\b(file:///[^ ]+)\b")

    def _highlight_logs_html(self, text: str) -> str:
        esc = html.escape(text)

        def repl_level(m: re.Match) -> str:
            lvl = m.group(1)
            cls = "t-info"
            if lvl in ("WARN", "WARNING"):
                cls = "t-warn"
            elif lvl in ("ERROR", "CRITICAL"):
                cls = "t-err"
            elif lvl == "DEBUG":
                cls = "t-dim"
            return f'<span class="{cls} t-bold">{lvl}</span>'

        esc = self._re_level.sub(repl_level, esc)
        esc = self._re_engine_tag.sub(r'<span class="t-cyan t-bold">azurmixd.engine</span>', esc)
        esc = self._re_sched_tag.sub(r'<span class="t-cyan t-bold">azurmixd.scheduler</span>', esc)
        esc = self._re_preprocess.sub(r'<span class="t-vio t-bold">preprocess:</span>', esc)
        esc = self._re_bridge.sub(r'<span class="t-vio">bridgeplan:</span>', esc)
        esc = self._re_aft.sub(lambda m: f'<span class="t-ok t-bold">{m.group(0)}</span>', esc)
        esc = self._re_icecast.sub(lambda m: f'<span class="t-cyan">{m.group(0)}</span>', esc)
        esc = self._re_uri.sub(r'<span class="t-dim">\1</span>', esc)

        return f'<div class="console-content">{esc}</div>'

    # ---------- Refresh ----------

    async def refresh_all(self) -> None:
        await self.refresh_runtime()
        await self.refresh_engine_env()
        await self.refresh_now()
        await self.refresh_upcoming()
        await self.refresh_logs()

    async def refresh_runtime(self) -> None:
        try:
            rt = await self._get_json("/panel/runtime")
        except Exception:
            self._set_docker_badge(ok=False, text="Docker: error")
            if self._rt_engine_tbl:
                self._rt_engine_tbl.set_content(self._runtime_table_html({"status": "error"}))
            if self._rt_sched_tbl:
                self._rt_sched_tbl.set_content(self._runtime_table_html({"status": "error"}))
            return

        docker_ok = bool(rt.get("docker_ping"))
        self._set_docker_badge(ok=docker_ok, text=f"Docker: {'OK' if docker_ok else 'DOWN'}")

        eng = rt.get("engine") or {}
        sch = rt.get("scheduler") or {}

        if self._rt_engine_tbl:
            self._rt_engine_tbl.set_content(self._runtime_table_html(eng))
        if self._rt_sched_tbl:
            self._rt_sched_tbl.set_content(self._runtime_table_html(sch))

    def _set_docker_badge(self, ok: bool, text: str) -> None:
        if self._docker_badge is None:
            return
        dot = "ok" if ok else "err"
        self._docker_badge.set_content(
            f'<span class="az-badge"><span class="az-dot {dot}"></span><span>{html.escape(text)}</span></span>'
        )

    async def refresh_engine_env(self) -> None:
        if self._env_frame is None:
            return
        try:
            data = await self._get_json("/panel/engine_env")
            env = data.get("environment") if isinstance(data, dict) else None
            if isinstance(env, dict):
                self._env_rows = [(k, str(env.get(k, ""))) for k in sorted(env.keys())]
            else:
                self._env_rows = [("error", str(data))]
        except Exception as e:
            self._env_rows = [("error", str(e))]
        self._render_env()

    def _env_clear_filter(self) -> None:
        if self._env_search:
            self._env_search.set_value("")
        self._render_env()

    def _render_env(self) -> None:
        if self._env_frame is None:
            return
        q = ""
        if self._env_search:
            q = (self._env_search.value or "").strip().lower()

        rows = self._env_rows
        if q:
            rows = [(k, v) for (k, v) in rows if q in k.lower() or q in v.lower()]

        self._env_frame.clear()
        with self._env_frame:
            if not rows:
                ui.html('<div style="padding:10px; opacity:.7;">—</div>')
                return
            for k, v in rows:
                k_e = html.escape(k)
                v_e = html.escape(v)
                ui.html(
                    f'<div class="env-row">'
                    f'  <div class="env-k" data-copy="{k_e}">{k_e}</div>'
                    f'  <div class="env-v" data-copy="{v_e}">{v_e}</div>'
                    f'</div>'
                )

    async def refresh_now(self) -> None:
        try:
            now = await self._get_json("/panel/now")
            self._now_title.set_text(now.get("title") or "—")
        except Exception:
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
                ui.html('<div style="opacity:.7; font-size: 12px;">—</div>')
                return
            for i, t in enumerate(titles, start=1):
                t_safe = html.escape(str(t))
                ui.html(
                    f'<div class="az-item"><span class="idx">{i}.</span> '
                    f'<span class="txt" data-copy="{t_safe}">{t_safe}</span></div>'
                )

    async def refresh_logs(self) -> None:
        try:
            eng = await self._get_text("/logs?service=engine&tail=200")
            if self._log_html_engine:
                self._log_html_engine.set_content(self._highlight_logs_html(eng))
        except Exception:
            if self._log_html_engine:
                self._log_html_engine.set_content('<div class="console-content">—</div>')

        try:
            sch = await self._get_text("/logs?service=scheduler&tail=200")
            if self._log_html_sched:
                self._log_html_sched.set_content(self._highlight_logs_html(sch))
        except Exception:
            if self._log_html_sched:
                self._log_html_sched.set_content('<div class="console-content">—</div>')

    def enable_autorefresh(self) -> None:
        if self._timer is not None:
            return
        self._timer = ui.timer(5.0, self.refresh_all)

    def disable_autorefresh(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._timer = None
