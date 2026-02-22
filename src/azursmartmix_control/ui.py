from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional

import csv
import html
import os
import re
import urllib.parse
from pathlib import Path

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
  --grid-gap: 18px;
}

*, *::before, *::after { box-sizing: border-box; }
html { font-size: 17px !important; }
body { font-size: 17px !important; }

html, body { background: var(--az-bg) !important; color: var(--az-text) !important; font-family: var(--az-font) !important; }
.q-page-container, .q-layout, .q-page { background: var(--az-bg) !important; }
.q-card, .q-table__container, .q-menu, .q-dialog__inner, .q-drawer { background: transparent !important; }

.q-tab-panels,
.q-tab-panel,
.q-panel,
.q-panel-parent,
.q-tabs,
.q-tabs__content,
.q-tab-panels .q-panel,
.q-tab-panels .q-panel-parent { background: transparent !important; }

.q-html, .q-html * { background: transparent !important; }

/* Quasar inputs dark */
.q-field__native,
.q-field__input,
.q-field__prefix,
.q-field__suffix,
.q-field__label,
.q-field__bottom,
.q-field__messages,
.q-placeholder,
.q-field__native::placeholder,
.q-field__input::placeholder { color: rgba(255,255,255,.92) !important; }

.q-field--outlined .q-field__control:before,
.q-field--outlined .q-field__control:after { border-color: rgba(255,255,255,.20) !important; }

.q-field--outlined .q-field__control,
.q-field__control { background: rgba(0,0,0,.18) !important; }

.q-field__marginal,
.q-select__dropdown-icon,
.q-icon { color: rgba(255,255,255,.78) !important; }

.q-menu,
.q-list,
.q-item,
.q-item__label { background: #151a22 !important; color: rgba(255,255,255,.92) !important; }

.az-topbar{
  background: linear-gradient(0deg, var(--az-blue) 0%, var(--az-blue-dark) 100%) !important;
  color: white !important;
  border-bottom: 1px solid rgba(255,255,255,.15);
  box-shadow: var(--az-shadow);
}
.az-topbar .az-brand { font-weight: 900; }
.az-topbar .az-sub { opacity: .85; font-weight: 600; }

.az-wrap{
  width: 90%;
  max-width: 90%;
  margin: 0 auto;
  padding: 18px 18px 28px 18px;
}

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
  font-weight:900; font-size:13px;
  border:1px solid var(--az-border);
  background: rgba(255,255,255,.05);
}
.az-dot{ width:10px; height:10px; border-radius:999px; display:inline-block; }
.az-dot.ok{ background: var(--az-green); }
.az-dot.err{ background: var(--az-red); }
.az-dot.warn{ background: var(--az-orange); }

.az-opbtn .q-btn{
  border-radius: 10px !important;
  font-weight: 950 !important;
  text-transform:none !important;
  padding: 6px 10px !important;
}
.az-opbtn .q-btn--outline{ border:1px solid rgba(255,255,255,.55) !important; color:white !important; }

.az-tabsbar{
  margin: 10px 0 18px 0;
  border: 1px solid rgba(255,255,255,.10);
  border-radius: 12px;
  overflow: hidden;
}
.az-tabsbar .q-tabs{ background: rgba(0,0,0,.15) !important; }

/* Settings layout */
.az-settings-toolbar{
  display:flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items:center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.az-settings-tools-left{
  display:flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items:center;
}
.az-settings-tools-right{
  display:flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items:center;
}
.az-settings-topcats{
  margin: 10px 0 12px 0;
  border: 1px solid rgba(255,255,255,.10);
  border-radius: 12px;
  overflow: hidden;
}
.az-settings-topcats .q-tabs{ background: rgba(0,0,0,.18) !important; }

.az-settings-grid{
  display:grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
@media (max-width: 1200px){
  .az-settings-grid{ grid-template-columns: 1fr; }
}

.set-box{
  border: 1px solid var(--az-border);
  border-radius: 12px;
  background: rgba(0,0,0,.10);
  overflow: hidden;
}
.set-box-h{
  padding: 10px 12px;
  font-weight: 950;
  border-bottom: 1px solid rgba(255,255,255,.08);
  display:flex;
  align-items:center;
  justify-content:space-between;
}
.set-box-h .meta{
  font-family: var(--az-mono);
  font-size: 12px;
  opacity:.75;
}
.set-box-b{ padding: 6px 10px; }

.set-row{
  display:grid;
  grid-template-columns: 520px 1fr;
  gap: 10px;
  padding: 10px 8px;
  border-bottom: 1px solid rgba(255,255,255,.06);
  align-items:flex-start;
}
.set-row:last-child{ border-bottom:none; }

.set-left{
  display:flex;
  flex-direction:column;
  gap: 4px;
  min-width: 0;
}

.set-name{
  font-size: 14px;
  font-weight: 950;
  color: rgba(255,255,255,.94);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.set-desc{
  font-size: 12px;
  color: var(--az-muted);
  line-height: 1.25;
  white-space: normal;
  word-break: break-word;
  opacity: .92;
}

.set-ctl{
  justify-self: end;
  width: 100%;
}

.az-inp .q-field__native,
.az-inp .q-field__input,
.az-inp input{
  color: rgba(255,255,255,.92) !important;
  font-family: var(--az-mono) !important;
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
    """AzurSmartMix Control UI.

    Contract:
    - Values are loaded/saved ONLY from/to azuramix.env via /compose/engine_env (API).
    - Layout (top_category/category/priority/name/explanation) is driven ONLY by azursmartmix_env_reference_v2.csv.
    - Join key is parameter name (CSV 'parameter' <-> env KEY).
    """

    _BOOL_TRUE_WORD = {"true", "yes", "y", "on", "enabled"}
    _BOOL_FALSE_WORD = {"false", "no", "n", "off", "disabled"}
    _BOOL_NUM = {"0", "1"}

    _BOOL_KEY_SUFFIXES = (
        "_ENABLE", "_ENABLED", "_DISABLE", "_DISABLED",
        "_DEBUG", "_VERBOSE", "_MUTE",
        "_ACCESS_LOG", "_LOG", "_LOGS",
        "_SAFE", "_STRICT", "_FORCE",
    )
    _BOOL_KEY_CONTAINS = ("_ENABLE_", "_ENABLED_", "_DISABLE_", "_DISABLED_", "_DEBUG_", "_ACCESS_LOG_")

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_base = settings.api_prefix.rstrip("/")
        self.timeout = httpx.Timeout(30.0, connect=3.0)

        self._timer = None

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

        # Settings state
        self._settings_advanced = False
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

        # CSV reference
        self._env_ref_by_key: Dict[str, Dict[str, str]] = {}
        self._category_order: List[str] = []
        self._topcats_order: List[str] = []

        self._compose_env_busy = False
        self._compose_env_format = "dict"

        self._load_env_reference_csv()

    # -------------------- CSV loader (layout only) --------------------

    def _load_env_reference_csv(self) -> None:
        candidates: List[str] = []
        env_path = (os.getenv("AZURSMARTMIX_ENV_REFERENCE_CSV") or "").strip()
        if env_path:
            candidates.append(env_path)

        try:
            candidates.append(str(Path(__file__).with_name("azursmartmix_env_reference_v2.csv")))
        except Exception:
            pass

        candidates.extend(
            [
                "/config/azursmartmix_env_reference_v2.csv",
                "/azuracast/azursmartmix_env_reference_v2.csv",
            ]
        )

        path: Optional[Path] = None
        for p in candidates:
            try:
                pp = Path(p)
                if pp.exists() and pp.is_file():
                    path = pp
                    break
            except Exception:
                continue

        if not path:
            self._env_ref_by_key = {}
            self._category_order = ["Other"]
            self._topcats_order = ["Main"]
            return

        ref: Dict[str, Dict[str, str]] = {}
        cat_order: List[str] = []
        seen_cat = set()
        top_order: List[str] = []
        seen_top = set()

        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row:
                    continue

                key = (row.get("parameter") or "").strip()
                if not key:
                    continue

                top_category = (row.get("top_category") or "Main").strip() or "Main"
                category = (row.get("category") or "Other").strip() or "Other"
                priority = (row.get("priority") or "secondary").strip().lower() or "secondary"
                if priority not in {"primary", "secondary"}:
                    priority = "secondary"
                english_name = (row.get("english_name") or key).strip() or key
                explanation = (row.get("explanation") or "").strip()

                ref[key] = {
                    "parameter": key,
                    "top_category": top_category,
                    "category": category,
                    "priority": priority,
                    "english_name": english_name,
                    "explanation": explanation,
                }

                if top_category not in seen_top:
                    seen_top.add(top_category)
                    top_order.append(top_category)

                if category not in seen_cat:
                    seen_cat.add(category)
                    cat_order.append(category)

        if "Other" not in seen_cat:
            cat_order.append("Other")

        if "Main" in top_order:
            top_order = ["Main"] + [x for x in top_order if x != "Main"]

        self._env_ref_by_key = ref
        self._category_order = cat_order
        self._topcats_order = top_order

    def _topcats_from_csv(self) -> List[str]:
        return list(self._topcats_order) if self._topcats_order else ["Main"]

    def _keys_for_topcat_from_csv(self, topcat: str) -> List[str]:
        out = []
        for k, meta in self._env_ref_by_key.items():
            tc = meta.get("top_category") or "Main"
            if tc == topcat:
                out.append(k)
        return out

    def _get_ref(self, key: str) -> Dict[str, str]:
        meta = self._env_ref_by_key.get(key)
        if meta:
            return meta
        return {
            "parameter": key,
            "top_category": "Main",
            "category": "Other",
            "priority": "secondary",
            "english_name": key,
            "explanation": "Unmapped parameter (missing from env reference CSV).",
        }

    # -------------------- bool/number typing helpers --------------------

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

    # -------------------- Build UI (minimal dashboard kept) --------------------

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

                self._btn_up = ui.button("Start", on_click=self.op_compose_up).props("unelevated color=positive")
                self._btn_down = ui.button("Stop", on_click=self.op_compose_down).props("unelevated color=negative")
                self._btn_recreate = ui.button("Recreate", on_click=self.op_compose_recreate).props("unelevated color=warning")
                self._btn_update = ui.button("Update", on_click=self.op_compose_update).props("outline")

                ui.separator().props("vertical").style("height:26px; opacity:.35;")
                ui.button("Refresh", on_click=self.refresh_settings).props("unelevated color=white text-color=primary")

        with ui.element("div").classes("az-wrap"):
            with ui.element("div").classes("az-tabsbar"):
                with ui.tabs().classes("w-full") as self._tabs:
                    ui.tab(self._tab_dashboard)
                    ui.tab(self._tab_settings)

            with ui.tab_panels(self._tabs, value=self._tab_settings).classes("w-full"):
                with ui.tab_panel(self._tab_dashboard):
                    ui.label("Dashboard (unchanged in this iteration)").style("opacity:.8;")
                with ui.tab_panel(self._tab_settings):
                    self._card_settings()

        ui.timer(0.2, self.refresh_settings, once=True)

    def _default_tag_from_image(self) -> str:
        s = (self.settings.azursmartmix_image or "").strip()
        if ":" in s:
            return s.rsplit(":", 1)[1].strip() or "latest"
        return "latest"

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

    # -------------------- Ops dialog (kept) --------------------

    def _build_ops_dialog(self) -> None:
        with ui.dialog() as d:
            self._ops_dialog = d
            with ui.card().classes("az-card").style("min-width: 920px; max-width: 1200px;"):
                with ui.element("div").classes("az-card-h"):
                    ui.label("Operations Console")
                    ui.button("Close", on_click=d.close).props("outline")
                with ui.element("div").classes("az-card-b"):
                    ui.label(f"cwd: {self.settings.azuramix_dir}").style("font-family: var(--az-mono); font-size: 13px; opacity:.85;")
                    ui.label(f"compose: {self.settings.azuramix_compose_file}").style("font-family: var(--az-mono); font-size: 13px; opacity:.65; margin-top: 2px;")
                    ui.separator().style("opacity:.25; margin: 10px 0;")
                    with ui.element("div").classes("console-frame").style("height: 520px;"):
                        self._ops_html = ui.html('<div class="console-content">—</div>')

    async def _post_text(self, path: str) -> str:
        url = f"http://127.0.0.1:{self.settings.ui_port}{self.settings.api_prefix.rstrip('/')}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(url)
            r.raise_for_status()
            return r.text

    async def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"http://127.0.0.1:{self.settings.ui_port}{self.settings.api_prefix.rstrip('/')}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, dict) else {"data": data}

    async def _run_op(self, label: str, path: str, clears_restart_hint: bool = False) -> None:
        if self._ops_busy:
            ui.notify("Operation already running", type="warning")
            return
        self._ops_busy = True
        try:
            if self._ops_dialog:
                self._ops_dialog.open()
            if self._ops_html:
                self._ops_html.set_content(f'<div class="console-content">{html.escape(f"== {label} ==\\nPOST {path}\\n\\nrunning...\\n")}</div>')
            txt = await self._post_text(path)
            if self._ops_html:
                self._ops_html.set_content(f'<div class="console-content">{html.escape(txt)}</div>')
            ui.notify(f"{label}: done", type="positive")
            if clears_restart_hint:
                self._set_restart_needed(False)
        except Exception as e:
            if self._ops_html:
                self._ops_html.set_content(f'<div class="console-content">{html.escape(f"== {label} ==\\nerror: {e}\\n")}</div>')
            ui.notify(f"{label}: error", type="negative")
        finally:
            self._ops_busy = False

    async def op_compose_down(self) -> None:
        await self._run_op("Stop (docker compose down)", "/ops/compose/down", clears_restart_hint=False)

    async def op_compose_up(self) -> None:
        await self._run_op("Start (docker compose up -d)", "/ops/compose/up", clears_restart_hint=True)

    async def op_compose_recreate(self) -> None:
        await self._run_op("Recreate (up -d --force-recreate)", "/ops/compose/recreate", clears_restart_hint=True)

    async def op_compose_update(self) -> None:
        tag = str(self._tag_value or "").strip()
        qs = ""
        if tag:
            qs = "?tag=" + urllib.parse.quote(tag, safe="")
        await self._run_op(f"Update (down + rm image:{tag or 'default'})", "/ops/compose/update" + qs, clears_restart_hint=True)

    # -------------------- Settings tab --------------------

    def _card_settings(self) -> None:
        with ui.element("div").classes("az-card").style("grid-column: 1 / -1; min-width: unset;"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Settings")
                ui.label("azuramix.env values + CSV layout").classes("text-xs").style("opacity:.85;")

            with ui.element("div").classes("az-card-b"):
                with ui.element("div").classes("az-settings-toolbar"):
                    with ui.element("div").classes("az-settings-tools-left"):
                        ui.label("Service: Engine (env_file)").style("opacity:.85; font-weight:900;")

                        ui.switch(
                            "Advanced",
                            value=self._settings_advanced,
                            on_change=self._on_settings_advanced_change,
                        ).props("dense")

                        self._settings_show_unmapped_switch = ui.switch(
                            "Show unmapped env vars",
                            value=self._settings_show_unmapped,
                            on_change=self._on_show_unmapped_change,
                        ).props("dense")

                        self._settings_search = ui.input(
                            placeholder="Filter (english name / param / explanation)…",
                            on_change=lambda _e: self._render_settings_grid(),
                        ).classes("az-inp").props("dense outlined dark").style("min-width: 360px;")

                    with ui.element("div").classes("az-settings-tools-right"):
                        ui.button("Reload", on_click=self.refresh_settings).props("outline")
                        ui.button("Save", on_click=self.save_settings).props("unelevated color=positive")

                self._settings_topcat_container = ui.element("div").classes("az-settings-topcats")

                ui.label(
                    "Layout is driven by azursmartmix_env_reference_v2.csv (top_category/category/priority). "
                    "Values are loaded/saved from/to azuramix.env. Restart/Recreate required."
                ).style("opacity:.75; margin-bottom: 10px;")

                self._settings_grid_container = ui.element("div").classes("az-settings-grid")

    def _on_settings_advanced_change(self, e) -> None:
        try:
            self._settings_advanced = bool(e.value)
        except Exception:
            self._settings_advanced = False
        self._render_settings_grid()

    def _on_show_unmapped_change(self, e) -> None:
        try:
            self._settings_show_unmapped = bool(e.value)
        except Exception:
            self._settings_show_unmapped = False
        self._render_settings_grid()

    def _on_topcat_change(self, e) -> None:
        try:
            self._settings_topcat_value = str(e.value).strip() if e.value is not None else None
        except Exception:
            self._settings_topcat_value = None
        self._render_settings_grid()

    def _build_topcat_tabs_from_csv(self) -> None:
        if not self._settings_topcat_container:
            return

        topcats = self._topcats_from_csv()
        if self._settings_topcat_value not in topcats:
            self._settings_topcat_value = topcats[0] if topcats else None

        self._settings_topcat_container.clear()
        with self._settings_topcat_container:
            with ui.tabs(value=self._settings_topcat_value, on_change=self._on_topcat_change).classes("w-full") as t:
                self._settings_topcat_tabs = t
                for tc in topcats:
                    ui.tab(tc)

    def _render_settings_grid(self) -> None:
        if not self._settings_grid_container:
            return

        # tabs always computed from CSV
        self._build_topcat_tabs_from_csv()
        selected_topcat = self._settings_topcat_value or (self._topcats_from_csv()[0] if self._topcats_from_csv() else "Main")

        env = self._settings_env_work or {}
        advanced = bool(self._settings_advanced)

        q = ""
        if self._settings_search:
            q = str(self._settings_search.value or "").strip().lower()

        self._settings_grid_container.clear()
        self._settings_inputs = {}

        # bucket by category: ONLY keys from CSV in this topcat
        keys_in_top = self._keys_for_topcat_from_csv(selected_topcat)

        buckets: Dict[str, List[str]] = {}
        for k in keys_in_top:
            meta = self._get_ref(k)
            cat = meta.get("category") or "Other"
            buckets.setdefault(cat, []).append(k)

        categories: List[str] = []
        # keep CSV category ordering, but only those with content in this topcat
        for c in self._category_order:
            if c in buckets:
                categories.append(c)
        for c in sorted(buckets.keys()):
            if c not in categories:
                categories.append(c)

        def key_sort(k: str) -> Tuple[int, str]:
            meta = self._get_ref(k)
            pr = meta.get("priority", "secondary")
            pr_rank = 0 if pr == "primary" else 1
            nm = meta.get("english_name", k)
            return (pr_rank, nm.lower())

        with self._settings_grid_container:
            for cat in categories:
                keys = list(buckets.get(cat, []))
                if not keys:
                    continue

                if not advanced:
                    keys = [k for k in keys if self._get_ref(k).get("priority") == "primary"]

                if q:
                    filtered: List[str] = []
                    for k in keys:
                        meta = self._get_ref(k)
                        hay = " ".join(
                            [
                                k.lower(),
                                (meta.get("english_name") or "").lower(),
                                (meta.get("explanation") or "").lower(),
                            ]
                        )
                        if q in hay:
                            filtered.append(k)
                    keys = filtered

                if not keys:
                    continue

                keys.sort(key=key_sort)

                with ui.element("div").classes("set-box"):
                    with ui.element("div").classes("set-box-h"):
                        ui.label(cat)
                        ui.label(f"{len(keys)} vars").classes("meta")

                    with ui.element("div").classes("set-box-b"):
                        for key in keys:
                            val = env.get(key, "")
                            self._render_setting_row(key, val)

            # optional: show env vars not in CSV
            if self._settings_show_unmapped:
                unmapped = sorted([k for k in env.keys() if k not in self._env_ref_by_key])
                if unmapped:
                    with ui.element("div").classes("set-box"):
                        with ui.element("div").classes("set-box-h"):
                            ui.label("Unmapped (env only)")
                            ui.label(f"{len(unmapped)} vars").classes("meta")
                        with ui.element("div").classes("set-box-b"):
                            for key in unmapped:
                                self._render_setting_row(key, env.get(key, ""))

    def _render_setting_row(self, key: str, val: str) -> None:
        def set_work(v: Any) -> None:
            self._settings_env_work[str(key)] = "" if v is None else str(v)

        meta = self._get_ref(key)
        english_name = meta.get("english_name", key) or key
        explanation = meta.get("explanation", "") or ""
        k_e = html.escape(str(key))
        name_e = html.escape(str(english_name))
        exp_e = html.escape(str(explanation))

        with ui.element("div").classes("set-row"):
            with ui.element("div").classes("set-left"):
                # only english_name + explanation; key is hidden but copyable
                ui.html(f'<div class="set-name" title="{k_e}" data-copy="{k_e}">{name_e}</div>')
                ui.html(f'<div class="set-desc">{exp_e if exp_e else "—"}</div>')

            b = self._parse_bool_like_key(key, val)
            if b is not None:
                sw = ui.switch(
                    value=bool(b),
                    on_change=lambda e: set_work(self._format_bool_like(val, bool(e.value))),
                ).props("dense").classes("set-ctl")
                self._settings_inputs[key] = sw
                return

            inp = ui.input(
                value=str(val),
                placeholder="value",
                on_change=lambda e: set_work(e.value),
            ).classes("az-inp").props("dense outlined dark")

            if self._is_number_like(val):
                inp.props("type=number")

            inp.classes("set-ctl")
            self._settings_inputs[key] = inp

    # -------------------- API: load/save env from azuramix.env --------------------

    async def refresh_settings(self) -> None:
        if not self._settings_topcat_container:
            return
        try:
            data = await self._get_json("/compose/engine_env")
            env = data.get("environment") if isinstance(data, dict) else None
            if not isinstance(env, dict):
                env = {}

            clean: Dict[str, str] = {}
            for k, v in env.items():
                if k is None:
                    continue
                kk = str(k).strip()
                if not kk:
                    continue
                clean[kk] = "" if v is None else str(v)

            self._settings_env_base = dict(clean)
            self._settings_env_work = dict(clean)

            # tabs from CSV only (but keep selection)
            topcats = self._topcats_from_csv()
            if self._settings_topcat_value not in topcats:
                self._settings_topcat_value = topcats[0] if topcats else "Main"

            self._render_settings_grid()
        except Exception as e:
            self._settings_env_base = {}
            self._settings_env_work = {"error": str(e)}
            self._render_settings_grid()

    async def save_settings(self) -> None:
        if self._compose_env_busy:
            ui.notify("Save busy", type="warning")
            return
        self._compose_env_busy = True
        try:
            out: Dict[str, str] = {}
            for k, v in (self._settings_env_work or {}).items():
                kk = str(k).strip()
                if not kk:
                    continue
                out[kk] = "" if v is None else str(v)

            payload = {"environment": out, "env_format_prefer": self._compose_env_format}
            r = await self._post_json("/compose/engine_env", payload)

            if r.get("ok"):
                self._set_restart_needed(True)
                ui.notify("Saved to azuramix.env. Restart/Recreate required.", type="warning")
                await self.refresh_settings()
            else:
                ui.notify("Save failed", type="negative")
        except Exception as e:
            ui.notify(f"Save error: {e}", type="negative")
        finally:
            self._compose_env_busy = False

    async def _get_json(self, path: str) -> Dict[str, Any]:
        url = f"http://127.0.0.1:{self.settings.ui_port}{self.settings.api_prefix.rstrip('/')}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, dict) else {"data": data}

    async def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"http://127.0.0.1:{self.settings.ui_port}{self.settings.api_prefix.rstrip('/')}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, dict) else {"data": data}
