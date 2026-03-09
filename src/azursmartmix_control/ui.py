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

/* +1 point globally */
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
.q-tab-panels .q-panel-parent {
  background: transparent !important;
}

.q-html,
.q-html * {
  background: transparent !important;
}

/* Force Quasar inputs to be dark */
.q-field__native,
.q-field__input,
.q-field__prefix,
.q-field__suffix,
.q-field__label,
.q-field__bottom,
.q-field__messages,
.q-placeholder,
.q-field__native::placeholder,
.q-field__input::placeholder {
  color: rgba(255,255,255,.92) !important;
}

.q-field--outlined .q-field__control:before,
.q-field--outlined .q-field__control:after {
  border-color: rgba(255,255,255,.20) !important;
}

.q-field--outlined .q-field__control,
.q-field__control {
  background: rgba(0,0,0,.18) !important;
}

.q-field__marginal,
.q-select__dropdown-icon,
.q-icon {
  color: rgba(255,255,255,.78) !important;
}

.q-menu,
.q-list,
.q-item,
.q-item__label {
  background: #151a22 !important;
  color: rgba(255,255,255,.92) !important;
}

.az-topbar{
  background: linear-gradient(0deg, var(--az-blue) 0%, var(--az-blue-dark) 100%) !important;
  color: white !important;
  border-bottom: 1px solid rgba(255,255,255,.15);
  box-shadow: var(--az-shadow);
}
.az-topbar .az-brand { font-weight: 900; }
.az-topbar .az-sub { opacity: .85; font-weight: 600; }

/* center + 90% width */
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

.az-list{ display:flex; flex-direction:column; gap:8px; }
.az-item{ padding: 10px 12px; border-radius: 10px; border: 1px solid var(--az-border); background: rgba(255,255,255,.04); }
.az-item .idx{ display:inline-block; min-width:24px; font-weight:950; color: rgba(255,255,255,.75); }
.az-item .txt{ font-weight:650; }

.rt-grid{ display:grid; grid-template-columns: 1fr 1fr; gap: 14px; align-items: stretch; }
@media (max-width: 900px){ .rt-grid{ grid-template-columns: 1fr; } }

.rt-box{
  border: 1px solid var(--az-border);
  border-radius: 10px;
  background: rgba(0,0,0,.10);
  overflow: hidden;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.rt-box-h{
  padding: 10px 12px;
  font-weight: 900;
  border-bottom: 1px solid rgba(255,255,255,.08);
  color: rgba(255,255,255,.92);
}
.rt-table{ width: 100%; border-collapse: collapse; font-size: 14px; table-layout: fixed; }
.rt-table tr td{
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255,255,255,.06);
  vertical-align: top;
}
.rt-table tr:last-child td{ border-bottom: none; }
.rt-k{ width: 132px; color: var(--az-muted); white-space: nowrap; }
.rt-v{ color: rgba(255,255,255,.92); font-family: var(--az-mono); word-break: break-word; width: 100%; }

.az-grid-3{ display:grid; grid-template-columns: .80fr 1.20fr; gap: var(--grid-gap); align-items: stretch; }
.az-grid-3 > .az-card{ height: 100%; }
@media (max-width: 1200px){ .az-grid-3{ grid-template-columns: 1fr; } }

.res-shell{ display:flex; flex-direction:column; gap:12px; }
.res-top{ display:grid; grid-template-columns: 1fr auto; gap:10px; align-items:end; }
.res-big{ font-size: 34px; font-weight: 950; line-height:1; }
.res-big .unit{ font-size: 15px; opacity:.72; margin-left: 4px; font-weight:800; }
.res-sub{ color: var(--az-muted); font-size: 13px; font-family: var(--az-mono); }
.res-pill{ display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px; border:1px solid var(--az-border); background: rgba(255,255,255,.04); font-size:12px; font-weight:900; }
.res-grid{ display:grid; grid-template-columns: 1fr 1fr; gap:12px; }
@media (max-width: 700px){ .res-grid{ grid-template-columns: 1fr; } }
.res-box{ border: 1px solid var(--az-border); border-radius: 12px; background: rgba(0,0,0,.12); padding: 12px; }
.res-box-h{ display:flex; align-items:center; justify-content:space-between; margin-bottom: 8px; font-weight:900; }
.res-box-h .mini{ color: var(--az-muted); font-size: 12px; font-weight:700; }
.res-bar{ height: 10px; width:100%; border-radius: 999px; overflow:hidden; background: rgba(255,255,255,.08); }
.res-bar > span{ display:block; height:100%; border-radius:999px; }
.res-bar-cpu > span{ background: linear-gradient(90deg, #22d3ee, #1e88e5); }
.res-bar-mem > span{ background: linear-gradient(90deg, #60a5fa, #a78bfa); }
.res-kpis{ display:flex; align-items:center; justify-content:space-between; gap:12px; margin-top:8px; font-size: 13px; }
.res-kpis .v{ font-family: var(--az-mono); font-weight: 900; color: rgba(255,255,255,.92); }

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
  font-size: 13px !important;
  line-height: 1.35 !important;
  color: rgba(255,255,255,.86) !important;
  white-space: pre-wrap !important;
  word-break: break-word !important;
  margin: 0 !important;
  padding: 0 !important;
}

.t-dim{ color: rgba(255,255,255,.45) !important; }
.t-info{ color: rgba(56, 189, 248, .95) !important; }
.t-warn{ color: rgba(245, 158, 11, .95) !important; }
.t-err{  color: rgba(239, 68, 68, .95) !important; }
.t-ok{   color: rgba(34, 197, 94, .95) !important; }
.t-vio{  color: rgba(167, 139, 250, .95) !important; }
.t-cyan{ color: rgba(34, 211, 238, .95) !important; }
.t-bold{ font-weight: 900 !important; }

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
  filter: invert(1) hue-rotate(180deg) saturate(1.2);
  opacity: 0.95;
}
.az-player .hint{
  margin-top: 8px;
  font-size: 13px;
  color: rgba(255,255,255,.65);
  font-family: var(--az-mono);
}

.np-meta{
  margin-top: 8px;
  display:flex;
  flex-direction:column;
  gap: 6px;
}
.np-line{
  font-family: var(--az-mono);
  font-size: 13px;
  color: rgba(255,255,255,.80);
}
.np-k{ color: rgba(255,255,255,.55); }
.np-v{ color: rgba(255,255,255,.92); font-weight: 800; }
.np-pill{
  display:inline-flex; align-items:center; gap:8px;
  padding: 5px 10px;
  border-radius: 999px;
  border:1px solid var(--az-border);
  background: rgba(255,255,255,.05);
}

.az-tabsbar{
  margin: 10px 0 18px 0;
  border: 1px solid rgba(255,255,255,.10);
  border-radius: 12px;
  overflow: hidden;
}
.az-tabsbar .q-tabs{
  background: rgba(0,0,0,.15) !important;
}

/* SETTINGS UI */
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
.az-settings-topcats .q-tabs{
  background: rgba(0,0,0,.18) !important;
}

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
.set-box-b{
  padding: 6px 10px;
}

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
  font-weight: 900;
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

        self._up_list_container = None

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

        # Settings UI: top_category sub-tabs (driven by CSV)
        self._settings_topcat_container = None
        self._settings_topcat_tabs = None
        self._settings_topcat_value: Optional[str] = None

        # Settings UI: show env-only keys (debug)
        self._settings_show_unmapped = False
        self._settings_show_unmapped_switch = None

        # CSV ordering for top_category
        self._topcats_order: List[str] = []

        self._env_ref_by_key: Dict[str, Dict[str, str]] = {}
        self._category_order: List[str] = []

        self._compose_env_busy = False
        self._compose_env_format = "dict"

        self._load_env_reference_csv()

    # -------------------- CSV reference loader --------------------

    def _load_env_reference_csv(self) -> None:
        """Load the env reference CSV (layout metadata only).

        Robustness goals:
        - Accept headers with spaces (e.g. 'top category') or underscores ('top_category').
        - Preserve ordering for category and top_category as they appear in CSV.
        - Join key is 'parameter' (env var name).
        """
        candidates: List[str] = []
        try:
            maybe = getattr(self.settings, "env_reference_csv", None)
            if isinstance(maybe, str) and maybe.strip():
                candidates.append(maybe.strip())
        except Exception:
            pass

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

        def norm_header(h: str) -> str:
            return re.sub(r"\s+", "_", str(h or "").strip().lower())

        ref: Dict[str, Dict[str, str]] = {}
        cat_order: List[str] = []
        top_order: List[str] = []
        seen_cat = set()
        seen_top = set()

        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                reader.fieldnames = [norm_header(h) for h in reader.fieldnames]

            for row in reader:
                if not row:
                    continue

                row_n = {norm_header(k): (v if v is not None else "") for k, v in row.items()}

                key = str(row_n.get("parameter", "")).strip()
                if not key:
                    continue

                # CSV column is "top category" (normalized to top_category) or "top_category"
                top_category = str(row_n.get("top_category", "")).strip() or "Main"
                category = str(row_n.get("category", "")).strip() or "Other"

                priority = str(row_n.get("priority", "")).strip().lower() or "secondary"
                if priority not in {"primary", "secondary"}:
                    priority = "secondary"

                english_name = str(row_n.get("english_name", "")).strip() or key
                explanation = str(row_n.get("explanation", "")).strip()

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
        elif not top_order:
            top_order = ["Main"]

        self._env_ref_by_key = ref
        self._category_order = cat_order
        self._topcats_order = top_order

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
            "explanation": "Unmapped parameter (not present in env reference CSV).",
        }

    def _topcats_from_csv(self) -> List[str]:
        """Top-level Settings tabs: driven by CSV ordering."""
        if self._topcats_order:
            return list(self._topcats_order)
        return ["Main"]

    def _keys_for_topcat_from_csv(self, topcat: str) -> List[str]:
        out: List[str] = []
        for k, meta in self._env_ref_by_key.items():
            tc = (meta.get("top_category") or "Main").strip() or "Main"
            if tc == topcat:
                out.append(k)
        return out

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

                ui.button("Refresh", on_click=self.refresh_visible).props("unelevated color=white text-color=primary")
                ui.button("Auto 5s", on_click=self.enable_autorefresh).props("outline")
                ui.button("Stop Auto", on_click=self.disable_autorefresh).props("outline")

        with ui.element("div").classes("az-wrap"):
            with ui.element("div").classes("az-tabsbar"):
                with ui.tabs(value=self._tab_dashboard, on_change=self._on_main_tab_change).classes("w-full") as self._tabs:
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
                    ui.label(f"cwd: {self.settings.azuramix_dir}").style("font-family: var(--az-mono); font-size: 13px; opacity:.85;")
                    ui.label(f"compose: {self.settings.azuramix_compose_file}").style("font-family: var(--az-mono); font-size: 13px; opacity:.65; margin-top: 2px;")
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
                self._ops_html.set_content(f'<div class="console-content">{html.escape(f"== {label} ==\\nPOST {path}\\n\\nrunning...\\n")}</div>')

            txt = await self._post_text(path)

            if self._ops_html:
                self._ops_html.set_content(f'<div class="console-content">{html.escape(txt)}</div>')

            ui.notify(f"{label}: done", type="positive")
            if clears_restart_hint:
                self._set_restart_needed(False)

            await self.refresh_dashboard()
        except Exception as e:
            if self._ops_html:
                self._ops_html.set_content(f'<div class="console-content">{html.escape(f"== {label} ==\\nerror: {e}\\n")}</div>')
            ui.notify(f"{label}: error", type="negative")
        finally:
            self._set_ops_busy(False)

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

    # -------------------- Dashboard cards --------------------

    def _card_runtime(self) -> None:
        with ui.element("div").classes("az-card"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Runtime Status")
                self._docker_badge = ui.html('<span class="az-badge"><span class="az-dot warn"></span><span>Docker: …</span></span>')
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
        tr = "".join(f'<tr><td class="rt-k">{html.escape(k)}</td><td class="rt-v" data-copy="{val}">{val}</td></tr>' for k, val in rows)
        return f'<table class="rt-table">{tr}</table>'

    def _card_resources(self) -> None:
        with ui.element("div").classes("az-card"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Resources")
                self._res_host_meta = ui.html('<span class="res-pill">host: …</span>')
            with ui.element("div").classes("az-card-b"):
                with ui.element("div").classes("res-shell"):
                    self._res_cpu_html = ui.html(self._resources_cpu_html({}))
                    self._res_mem_html = ui.html(self._resources_mem_html({}))

    @staticmethod
    def _fmt_bytes_gb(value: Any) -> str:
        try:
            n = float(value)
            if n <= 0:
                return "0.00 GB"
            return f"{n / (1024 ** 3):.2f} GB"
        except Exception:
            return "—"

    def _resources_cpu_html(self, data: Dict[str, Any]) -> str:
        cpu = data.get("cpu") if isinstance(data.get("cpu"), dict) else {}
        loadavg = data.get("loadavg") if isinstance(data.get("loadavg"), dict) else {}
        pct = cpu.get("percent")
        pct_num = float(pct) if isinstance(pct, (int, float)) else 0.0
        pct_txt = f"{pct_num:.2f}" if isinstance(pct, (int, float)) else "—"
        l1 = loadavg.get("one")
        l5 = loadavg.get("five")
        load_txt = f"{l1:.2f} / {l5:.2f}" if isinstance(l1, (int, float)) and isinstance(l5, (int, float)) else "—"
        width = max(0.0, min(100.0, pct_num))
        return (
            '<div class="res-box">'
            '<div class="res-box-h"><span>CPU</span><span class="mini">load 1/5m</span></div>'
            '<div class="res-top">'
            f'<div class="res-big">{pct_txt}<span class="unit">%</span></div>'
            f'<div class="res-sub">{html.escape(load_txt)}</div>'
            '</div>'
            f'<div class="res-bar res-bar-cpu"><span style="width:{width:.2f}%;"></span></div>'
            '<div class="res-kpis">'
            f'<div><span class="t-dim">sample</span> <span class="v">{html.escape(str(cpu.get("sample") or "—"))}</span></div>'
            f'<div><span class="t-dim">source</span> <span class="v">{html.escape(str(data.get("source") or "—"))}</span></div>'
            '</div>'
            '</div>'
        )

    def _resources_mem_html(self, data: Dict[str, Any]) -> str:
        mem = data.get("memory") if isinstance(data.get("memory"), dict) else {}
        used = mem.get("used_bytes")
        total = mem.get("total_bytes")
        avail = mem.get("available_bytes")
        cached = mem.get("cached_bytes")
        pct = mem.get("used_percent")
        pct_num = float(pct) if isinstance(pct, (int, float)) else 0.0
        pct_txt = f"{pct_num:.2f}" if isinstance(pct, (int, float)) else "—"
        width = max(0.0, min(100.0, pct_num))
        return (
            '<div class="res-box">'
            '<div class="res-box-h"><span>Memory</span><span class="mini">used / total</span></div>'
            '<div class="res-top">'
            f'<div class="res-big">{html.escape(self._fmt_bytes_gb(used))}</div>'
            f'<div class="res-sub">{pct_txt}%</div>'
            '</div>'
            f'<div class="res-bar res-bar-mem"><span style="width:{width:.2f}%;"></span></div>'
            '<div class="res-grid">'
            f'<div class="res-kpis"><div><span class="t-dim">total</span> <span class="v">{html.escape(self._fmt_bytes_gb(total))}</span></div><div><span class="t-dim">avail</span> <span class="v">{html.escape(self._fmt_bytes_gb(avail))}</span></div></div>'
            f'<div class="res-kpis"><div><span class="t-dim">cached</span> <span class="v">{html.escape(self._fmt_bytes_gb(cached))}</span></div><div><span class="t-dim">used</span> <span class="v">{pct_txt}%</span></div></div>'
            '</div>'
            '</div>'
        )

    def _card_now(self) -> None:
        stream_url = self._stream_public_url()
        mount = getattr(self.settings, "icecast_mount", "/gst-test.mp3")
        with ui.element("div").classes("az-card"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Now Playing")
                ui.label(str(mount)).classes("text-xs").style("opacity:.85;")
            with ui.element("div").classes("az-card-b"):
                self._now_title = ui.label("—").classes("text-xl").style("font-weight: 950; margin: 2px 0 0 0;")
                self._now_meta = ui.html(self._now_meta_html({}))
                self._now_player = ui.html(self._player_html(stream_url))
                ui.label("Sources: Icecast(observed) + scheduler NEXT + engine STREAM_START hint").style("opacity:.7; margin-top: 10px;")

    def _now_meta_html(self, now: Dict[str, Any]) -> str:
        playlist_eff = now.get("playlist_effective")
        pl_txt = html.escape(str(playlist_eff)) if playlist_eff else "—"

        predicted = now.get("predicted_next") if isinstance(now.get("predicted_next"), dict) else None
        pred_title = "—"
        pred_pl = "—"
        if predicted:
            pred_title = html.escape(str(predicted.get("title_display") or predicted.get("title") or "—"))
            pred_pl = html.escape(str(predicted.get("playlist") or "—"))

        ss = now.get("engine_stream_start") if isinstance(now.get("engine_stream_start"), dict) else None
        hint = ""
        if ss and ss.get("ok") and ss.get("recent"):
            age = ss.get("age_s")
            age_txt = f"{age}s" if isinstance(age, int) else "recent"
            hint = f'<span class="np-pill"><span class="t-ok t-bold">STREAM_START</span><span class="t-dim">({html.escape(age_txt)})</span></span>'
        elif ss and ss.get("ok") and ss.get("line"):
            age = ss.get("age_s")
            age_txt = f"{age}s" if isinstance(age, int) else ""
            hint = f'<span class="np-pill"><span class="t-dim">last STREAM_START</span><span class="t-dim">{html.escape(age_txt)}</span></span>'

        return (
            '<div class="np-meta">'
            f'  <div class="np-line"><span class="np-k">playlist:</span> <span class="np-v" data-copy="{pl_txt}">{pl_txt}</span></div>'
            f'  <div class="np-line"><span class="np-k">next(pred):</span> <span class="np-v" data-copy="{pred_title}">{pred_title}</span>'
            f'    <span class="t-dim">|</span> <span class="np-k">pl:</span> <span class="np-v" data-copy="{pred_pl}">{pred_pl}</span></div>'
            f'  <div class="np-line">{hint}</div>'
            "</div>"
        )

    def _player_html(self, url: str) -> str:
        u = html.escape(url)
        return (
            f'<div class="az-player">'
            f'  <audio controls preload="none" crossorigin="anonymous">'
            f'    <source src="{u}" type="audio/mpeg" />'
            f"  </audio>"
            f'  <div class="hint" data-copy="{u}">{u}</div>'
            f"</div>"
        )

    def _card_upcoming(self) -> None:
        with ui.element("div").classes("az-card"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Upcoming")
                ui.label("from scheduler NEXT log").classes("text-xs").style("opacity:.85;")
            with ui.element("div").classes("az-card-b"):
                self._up_list_container = ui.element("div").classes("az-list")

    def _card_logs(self) -> None:
        with ui.element("div").classes("az-card").style("grid-column: 1 / -1;"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Logs")
                ui.label("tail=200").classes("text-xs").style("opacity:.85;")
            with ui.element("div").classes("az-card-b"):
                with ui.tabs().classes("w-full") as tabs:
                    ui.tab("engine")
                    ui.tab("scheduler")

                with ui.tab_panels(tabs, value="engine").classes("w-full"):
                    with ui.tab_panel("engine"):
                        with ui.element("div").classes("console-frame").style("background: rgba(0,0,0,.55) !important;"):
                            self._log_html_engine = ui.html('<div class="console-content">—</div>')
                    with ui.tab_panel("scheduler"):
                        with ui.element("div").classes("console-frame").style("background: rgba(0,0,0,.55) !important;"):
                            self._log_html_sched = ui.html('<div class="console-content">—</div>')

    # -------------------- Settings tab --------------------

    def _card_settings(self) -> None:
        with ui.element("div").classes("az-card").style("grid-column: 1 / -1; min-width: unset;"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Settings")
                ui.label("azuramix.env (CSV layout)").classes("text-xs").style("opacity:.85;")

            with ui.element("div").classes("az-card-b"):
                with ui.element("div").classes("az-settings-toolbar"):
                    with ui.element("div").classes("az-settings-tools-left"):

                        self._settings_advanced_switch = ui.switch(
                            "Advanced",
                            value=self._settings_advanced,
                            on_change=self._on_settings_advanced_change,
                        ).props("dense")

                        self._settings_search = ui.input(
                            placeholder="Filter (name / key / explanation)…",
                            on_change=lambda _e: self._render_settings_grid(),
                        ).classes("az-inp").props("dense outlined dark").style("min-width: 320px;")

                    with ui.element("div").classes("az-settings-tools-right"):
                        ui.button("Reload", on_click=self.refresh_settings).props("outline")
                        ui.button("Save", on_click=self.save_settings).props("unelevated color=positive")

                # Top-category sub-tabs (driven by CSV)
                self._settings_topcat_container = ui.element("div").classes("az-settings-topcats")

                ui.label(
                    "Primary vars are always visible. Secondary vars require Advanced=ON. "
                    "Layout (top/category/priority) comes from azursmartmix_env_reference_v2.csv; "
                    "values are loaded/saved from/to azuramix.env (restart/recreate required)."
                ).style("opacity:.75; margin-bottom: 10px;")

                self._settings_grid_container = ui.element("div").classes("az-settings-grid")

    def _on_settings_service_change(self, e) -> None:
        try:
            self._settings_service = str(e.value).strip() or "engine"
        except Exception:
            self._settings_service = "engine"
        if self._settings_search:
            self._settings_search.set_value("")
        ui.timer(0.01, self.refresh_settings, once=True)

    def _on_settings_advanced_change(self, e) -> None:
        try:
            self._settings_advanced = bool(e.value)
        except Exception:
            self._settings_advanced = False
        self._render_settings_grid()

    def _on_settings_show_unmapped_change(self, e) -> None:
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

    def _build_topcat_tabs(self) -> None:
        if not self._settings_topcat_container:
            return
        topcats = self._topcats_from_csv()
        if self._settings_topcat_value not in topcats:
            self._settings_topcat_value = topcats[0] if topcats else "Main"
        self._settings_topcat_container.clear()
        with self._settings_topcat_container:
            with ui.tabs(value=self._settings_topcat_value, on_change=self._on_topcat_change).classes("w-full") as t:
                self._settings_topcat_tabs = t
                for tc in topcats:
                    ui.tab(tc)

    def _render_settings_grid(self) -> None:
        if not self._settings_grid_container:
            return

        # Tabs are driven by CSV only
        self._build_topcat_tabs()
        selected_topcat = self._settings_topcat_value or (self._topcats_from_csv()[0] if self._topcats_from_csv() else "Main")

        self._settings_grid_container.clear()
        self._settings_inputs = {}

        q = ""
        if self._settings_search:
            q = str(self._settings_search.value or "").strip().lower()

        advanced = bool(self._settings_advanced)
        env = self._settings_env_work or {}

        keys_in_top = self._keys_for_topcat_from_csv(str(selected_topcat))

        buckets: Dict[str, List[str]] = {}
        for k in keys_in_top:
            meta = self._get_ref(k)
            cat = meta.get("category", "Other") or "Other"
            buckets.setdefault(cat, []).append(k)

        categories: List[str] = []
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
                # keep key hidden; copyable by clicking the title
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

    async def refresh_settings(self) -> None:
        svc = self._settings_service or "engine"
        path = self._compose_env_endpoint(svc)
        try:
            data = await self._get_json(path)
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

        svc = self._settings_service or "engine"
        path = self._compose_env_endpoint(svc)

        self._compose_env_busy = True
        try:
            out: Dict[str, str] = {}
            for k, v in (self._settings_env_work or {}).items():
                kk = str(k).strip()
                if not kk:
                    continue
                out[kk] = "" if v is None else str(v)

            payload = {"environment": out, "env_format_prefer": self._compose_env_format}
            r = await self._post_json(path, payload)

            if r.get("ok"):
                self._set_restart_needed(True)
                ui.notify("Saved. Restart/Recreate required.", type="warning")
                await self.refresh_settings()
            else:
                ui.notify("Save failed", type="negative")
        except Exception as e:
            ui.notify(f"Save error: {e}", type="negative")
        finally:
            self._compose_env_busy = False

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

    async def refresh_dashboard(self) -> None:
        await self.refresh_resources()
        await self.refresh_runtime()
        await self.refresh_now()
        await self.refresh_upcoming()
        await self.refresh_logs()

    async def refresh_resources(self) -> None:
        try:
            data = await self._get_json("/panel/resources")
        except Exception:
            data = {}

        if self._res_host_meta:
            src = html.escape(str(data.get("source") or "host"))
            self._res_host_meta.set_content(f'<span class="res-pill">source: {src}</span>')
        if self._res_cpu_html:
            self._res_cpu_html.set_content(self._resources_cpu_html(data if isinstance(data, dict) else {}))
        if self._res_mem_html:
            self._res_mem_html.set_content(self._resources_mem_html(data if isinstance(data, dict) else {}))

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
        self._docker_badge.set_content(f'<span class="az-badge"><span class="az-dot {dot}"></span><span>{html.escape(text)}</span></span>')

    async def refresh_now(self) -> None:
        try:
            now = await self._get_json("/panel/now")
            title = now.get("title_effective") or now.get("title_observed") or "—"
            if self._now_title:
                self._now_title.set_text(title)
            if self._now_meta:
                self._now_meta.set_content(self._now_meta_html(now if isinstance(now, dict) else {}))
        except Exception:
            if self._now_title:
                self._now_title.set_text("—")
            if self._now_meta:
                self._now_meta.set_content(self._now_meta_html({}))

    async def refresh_upcoming(self) -> None:
        if self._up_list_container is None:
            return
        try:
            up = await self._get_json("/panel/upcoming?n=10")
            items = up.get("upcoming") or []
            if not isinstance(items, list):
                items = []
        except Exception:
            items = []

        self._up_list_container.clear()
        with self._up_list_container:
            if not items:
                ui.html('<div style="opacity:.7;">—</div>')
                return
            for i, it in enumerate(items, start=1):
                if not isinstance(it, dict):
                    continue
                title = str(it.get("title_display") or it.get("title") or "—")
                playlist = str(it.get("playlist") or "—")
                ts = str(it.get("ts") or "")

                title_e = html.escape(title)
                playlist_e = html.escape(playlist)
                ts_e = html.escape(ts)
                tail = f' <span class="t-dim">[{ts_e}]</span>' if ts else ""
                ui.html(
                    f'<div class="az-item"><span class="idx">{i}.</span> '
                    f'<span class="txt" data-copy="{title_e}">{title_e}</span> '
                    f'<span class="t-dim">|</span> '
                    f'<span class="t-cyan t-bold" data-copy="{playlist_e}">{playlist_e}</span>'
                    f'{tail}'
                    f"</div>"
                )

    async def refresh_logs(self) -> None:
        try:
            eng = await self._get_text("/logs?service=engine&tail=200")
            if self._log_html_engine:
                self._log_html_engine.set_content(f'<div class="console-content">{html.escape(eng)}</div>')
        except Exception:
            if self._log_html_engine:
                self._log_html_engine.set_content('<div class="console-content">—</div>')

        try:
            sch = await self._get_text("/logs?service=scheduler&tail=200")
            if self._log_html_sched:
                self._log_html_sched.set_content(f'<div class="console-content">{html.escape(sch)}</div>')
        except Exception:
            if self._log_html_sched:
                self._log_html_sched.set_content('<div class="console-content">—</div>')


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
