# src/azursmartmix_control/ui.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

import html
import json
import urllib.parse

import httpx
from nicegui import ui

from azursmartmix_control.config import Settings
from azursmartmix_control.ui_assets import AZURA_CSS, AZURA_JS
from azursmartmix_control.ui_dashboard import DashboardMixin
from azursmartmix_control.ui_mountpoints import MountpointsMixin
from azursmartmix_control.ui_settings import SettingsMixin


class ControlUI(MountpointsMixin, SettingsMixin, DashboardMixin):
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

        self._prev_container = None
        self._prev_source = None

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
        self._client_sync_badge = None

        self._tabs = None
        self._tab_dashboard = "Dashboard"
        self._tab_history = "History"
        self._tab_library = "Library"
        self._tab_mountpoints = "Mountpoints"
        self._tab_settings = "Settings"

        self._library_playlist_container = None
        self._library_mounts_html = None
        self._library_media_html = None
        self._library_media_title = None
        self._library_media_page_label = None
        self._library_media_prev_btn = None
        self._library_media_next_btn = None
        self._library_busy = False
        self._library_playlists_rows: List[Dict[str, Any]] = []
        self._library_selected_playlist_id: Optional[int] = None
        self._library_selected_playlist_name: Optional[str] = None
        self._library_media_page = 1
        self._library_media_page_size = 50
        self._library_media_total = 0
        self._library_media_total_pages = 1

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

        # Mountpoints state must be explicit after factorisation.
        self._mount_cfg_base: List[Dict[str, Any]] = []
        self._mount_cfg_work: List[Dict[str, Any]] = []
        self._mount_cfg_selected_idx: Optional[int] = None
        self._mount_cfg_busy = False
        self._mount_cfg_list_container = None
        self._mount_cfg_editor_container = None
        self._mount_cfg_meta = None

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

    # -------------------- Library (read-only, paginated media explorer) --------------------

    def _library_mountpoints_html(self, data: Dict[str, Any]) -> str:
        if not isinstance(data, dict) or not data.get("ok"):
            err = html.escape(str((data or {}).get("error") or "—"))
            return f'<div class="az-list"><div class="az-item"><span class="txt">error: {err}</span></div></div>'

        items = data.get("items") or []
        if not isinstance(items, list) or not items:
            return '<div class="az-list"><div class="az-item"><span class="txt">—</span></div></div>'

        rows: List[str] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            name = html.escape(str(it.get("name") or it.get("display_name") or "—"))
            path = html.escape(str(it.get("path") or "—"))
            fmt = html.escape(str(it.get("format") or "—"))
            bitrate = html.escape(str(it.get("bitrate") if it.get("bitrate") is not None else "—"))
            listeners = html.escape(str(it.get("listeners") if it.get("listeners") is not None else "—"))
            default_badge = '<span class="az-up-badge runtime">DEFAULT</span>' if bool(it.get("is_default")) else ''
            public_badge = '<span class="az-up-badge tempo">PUBLIC</span>' if bool(it.get("is_public")) else ''

            meta = (
                f'<span class="az-up-chip playlist"><span>PATH</span><span data-copy="{path}">{path}</span></span>'
                f'<span class="az-up-chip"><span>FMT</span><span data-copy="{fmt}">{fmt}</span></span>'
                f'<span class="az-up-chip bpm"><span>KBPS</span><span data-copy="{bitrate}">{bitrate}</span></span>'
                f'<span class="az-up-chip"><span>LISTENERS</span><span data-copy="{listeners}">{listeners}</span></span>'
            )

            rows.append(
                '<div class="az-item">'
                '  <div class="az-up-item">'
                '    <div class="az-up-head">'
                '      <div class="az-up-main">'
                f'        <div class="az-up-title" data-copy="{name}">{name}</div>'
                f'        <div class="az-up-meta">{default_badge}{public_badge}{meta}</div>'
                '      </div>'
                '    </div>'
                '  </div>'
                '</div>'
            )

        return f'<div class="az-list">{"".join(rows)}</div>'

    def _library_media_html_content(self, data: Dict[str, Any]) -> str:
        if not self._library_selected_playlist_id:
            return '<div class="az-list"><div class="az-item"><span class="txt">Select a playlist to browse its files.</span></div></div>'

        if not isinstance(data, dict) or not data.get("ok"):
            err = html.escape(str((data or {}).get("error") or "—"))
            return f'<div class="az-list"><div class="az-item"><span class="txt">error: {err}</span></div></div>'

        items = data.get("items") or []
        if not isinstance(items, list) or not items:
            return '<div class="az-list"><div class="az-item"><span class="txt">No files in this page.</span></div></div>'

        rows: List[str] = []
        for it in items:
            if not isinstance(it, dict):
                continue

            title_raw = str(it.get("title_display") or it.get("title") or "").strip()
            artist_raw = str(it.get("artist") or "").strip()
            album_raw = str(it.get("album") or "").strip()
            length_raw = str(it.get("length_text") or "").strip()

            if artist_raw and title_raw:
                display_title_raw = f"{artist_raw} - {title_raw}"
            else:
                display_title_raw = artist_raw or title_raw or "—"

            display_title = html.escape(display_title_raw)
            artist = html.escape(artist_raw or "—")
            album = html.escape(album_raw or "—")
            length_text = html.escape(length_raw or "—")

            meta = (
                f'<span class="az-up-chip bpm"><span>DUR</span><span data-copy="{length_text}">{length_text}</span></span>'
                f'<span class="az-up-chip"><span>ARTIST</span><span data-copy="{artist}">{artist}</span></span>'
                f'<span class="az-up-chip"><span>ALBUM</span><span data-copy="{album}">{album}</span></span>'
            )

            rows.append(
                '<div class="az-item">'
                '  <div class="az-up-item">'
                '    <div class="az-up-head">'
                '      <div class="az-up-main">'
                f'        <div class="az-up-title" data-copy="{display_title}">{display_title}</div>'
                f'        <div class="az-up-meta">{meta}</div>'
                '      </div>'
                '    </div>'
                '  </div>'
                '</div>'
            )

        return f'<div class="az-list">{"".join(rows)}</div>'

    def _render_library_playlists(self) -> None:
        if self._library_playlist_container is None:
            return

        self._library_playlist_container.clear()

        rows = self._library_playlists_rows or []
        if not rows:
            with self._library_playlist_container:
                ui.html('<div class="az-list"><div class="az-item"><span class="txt">—</span></div></div>')
            return

        with self._library_playlist_container:
            for it in rows:
                pid = it.get("id")
                name = str(it.get("name") or "—")
                short_name = str(it.get("short_name") or "—")
                ptype = str(it.get("type") or "—")
                source = str(it.get("source") or "—")
                order = str(it.get("order") or "—")
                weight = str(it.get("weight") if it.get("weight") is not None else "—")
                num_songs = str(it.get("num_songs") if it.get("num_songs") is not None else "—")
                enabled = bool(it.get("is_enabled"))
                jingle = bool(it.get("is_jingle"))
                selected = pid == self._library_selected_playlist_id

                with ui.element("div").classes("az-item"):
                    with ui.element("div").classes("az-up-item"):
                        with ui.element("div").classes("az-up-head"):
                            with ui.element("div").classes("az-up-main"):
                                row = ui.row().classes("items-center justify-between w-full")
                                with row:
                                    btn = ui.button(
                                        name,
                                        on_click=lambda _e=None, pid=pid, name=name: self._select_library_playlist(pid, name),
                                    ).props("flat no-caps")
                                    btn.classes("text-left")
                                    btn.style(
                                        "font-weight: 850; justify-content:flex-start; padding:0; min-height:auto; "
                                        + ("color: var(--az-cyan);" if selected else "color: rgba(255,255,255,.96);")
                                    )
                                    with ui.row().classes("items-center gap-2"):
                                        ui.html(
                                            f'<span class="az-up-badge {"runtime" if enabled else ""}">{html.escape("ENABLED" if enabled else "DISABLED")}</span>'
                                        )
                                        if jingle:
                                            ui.html('<span class="az-up-badge tempo">JINGLE</span>')
                                        if selected:
                                            ui.html('<span class="az-up-badge runtime">SELECTED</span>')

                                ui.html(
                                    '<div class="az-up-meta">'
                                    f'<span class="az-up-chip playlist"><span>ID</span><span data-copy="{html.escape(str(pid if pid is not None else "—"))}">{html.escape(str(pid if pid is not None else "—"))}</span></span>'
                                    f'<span class="az-up-chip"><span>SHORT</span><span data-copy="{html.escape(short_name)}">{html.escape(short_name)}</span></span>'
                                    f'<span class="az-up-chip"><span>TYPE</span><span data-copy="{html.escape(ptype)}">{html.escape(ptype)}</span></span>'
                                    f'<span class="az-up-chip"><span>SRC</span><span data-copy="{html.escape(source)}">{html.escape(source)}</span></span>'
                                    f'<span class="az-up-chip"><span>ORDER</span><span data-copy="{html.escape(order)}">{html.escape(order)}</span></span>'
                                    f'<span class="az-up-chip bpm"><span>TRACKS</span><span data-copy="{html.escape(num_songs)}">{html.escape(num_songs)}</span></span>'
                                    f'<span class="az-up-chip delta"><span>W</span><span data-copy="{html.escape(weight)}">{html.escape(weight)}</span></span>'
                                    '</div>'
                                )

    def _sync_library_media_controls(self) -> None:
        title = "Playlist Files"
        if self._library_selected_playlist_name:
            title = f"Playlist Files — {self._library_selected_playlist_name}"
        if self._library_media_title:
            self._library_media_title.set_text(title)

        label = f"Page {self._library_media_page}/{self._library_media_total_pages} • {self._library_media_total} files"
        if self._library_media_page_label:
            self._library_media_page_label.set_text(label)

        if self._library_media_prev_btn:
            if self._library_selected_playlist_id and self._library_media_page > 1:
                self._library_media_prev_btn.enable()
            else:
                self._library_media_prev_btn.disable()

        if self._library_media_next_btn:
            if self._library_selected_playlist_id and self._library_media_page < self._library_media_total_pages:
                self._library_media_next_btn.enable()
            else:
                self._library_media_next_btn.disable()

    def _card_library(self) -> None:
        with ui.element("div").classes("az-grid"):
            with ui.element("div").classes("az-card"):
                with ui.element("div").classes("az-card-h"):
                    ui.label("AzuraCast Playlists")
                    ui.button("Refresh", on_click=self.refresh_library).props("outline")
                with ui.element("div").classes("az-card-b"):
                    self._library_playlist_container = ui.column().classes("w-full")
                    self._render_library_playlists()

            with ui.element("div").classes("az-card"):
                with ui.element("div").classes("az-card-h"):
                    self._library_media_title = ui.label("Playlist Files")
                    with ui.row().classes("items-center gap-2"):
                        self._library_media_prev_btn = ui.button("Prev", on_click=self._library_prev_page).props("outline")
                        self._library_media_next_btn = ui.button("Next", on_click=self._library_next_page).props("outline")
                        self._library_media_page_label = ui.label("Page 1/1 • 0 files").classes("text-xs").style("opacity:.85;")
                with ui.element("div").classes("az-card-b"):
                    self._library_media_html = ui.html(
                        '<div class="az-list"><div class="az-item"><span class="txt">Select a playlist to browse its files.</span></div></div>'
                    )

        self._sync_library_media_controls()

    async def _select_library_playlist(self, playlist_id: Optional[int], playlist_name: str) -> None:
        if playlist_id is None:
            return
        self._library_selected_playlist_id = int(playlist_id)
        self._library_selected_playlist_name = str(playlist_name or "").strip() or f"Playlist {playlist_id}"
        self._library_media_page = 1
        self._render_library_playlists()
        await self.refresh_library_media()

    async def _library_prev_page(self) -> None:
        if not self._library_selected_playlist_id or self._library_media_page <= 1:
            return
        self._library_media_page -= 1
        await self.refresh_library_media()

    async def _library_next_page(self) -> None:
        if not self._library_selected_playlist_id or self._library_media_page >= self._library_media_total_pages:
            return
        self._library_media_page += 1
        await self.refresh_library_media()

    async def refresh_library_media(self) -> None:
        if self._library_media_html is None:
            return

        if not self._library_selected_playlist_id:
            self._library_media_total = 0
            self._library_media_total_pages = 1
            self._library_media_html.set_content(
                '<div class="az-list"><div class="az-item"><span class="txt">Select a playlist to browse its files.</span></div></div>'
            )
            self._sync_library_media_controls()
            return

        path = (
            "/azuracast/media?"
            + urllib.parse.urlencode(
                {
                    "playlist_id": self._library_selected_playlist_id,
                    "page": self._library_media_page,
                    "page_size": self._library_media_page_size,
                }
            )
        )

        try:
            data = await self._get_json(path)
        except Exception as e:
            data = {"ok": False, "error": str(e)}

        self._library_media_total = int(data.get("total") or 0) if isinstance(data, dict) else 0
        total_pages = int(data.get("total_pages") or 1) if isinstance(data, dict) else 1
        self._library_media_total_pages = max(1, total_pages)

        if self._library_media_page > self._library_media_total_pages:
            self._library_media_page = self._library_media_total_pages

        self._library_media_html.set_content(
            self._library_media_html_content(data if isinstance(data, dict) else {})
        )
        self._sync_library_media_controls()

    async def refresh_library(self) -> None:
        if self._library_busy:
            return
        self._library_busy = True
        try:
            playlists = await self._get_json("/azuracast/playlists")
        except Exception as e:
            playlists = {"ok": False, "error": str(e)}

        if isinstance(playlists, dict) and playlists.get("ok") and isinstance(playlists.get("items"), list):
            self._library_playlists_rows = [it for it in playlists.get("items") or [] if isinstance(it, dict)]
        else:
            self._library_playlists_rows = []

        if self._library_selected_playlist_id is not None:
            known_ids = {it.get("id") for it in self._library_playlists_rows}
            if self._library_selected_playlist_id not in known_ids:
                self._library_selected_playlist_id = None
                self._library_selected_playlist_name = None
                self._library_media_page = 1

        self._render_library_playlists()

        await self.refresh_library_media()
        self._library_busy = False

    def build(self) -> None:
        ui.add_head_html(f"<style>{AZURA_CSS}</style>")
        ui.add_head_html(f"<script>window.azApiBase = {json.dumps(self.api_base)};</script>")
        ui.add_head_html(f"<script>{AZURA_JS}</script>")
        ui.page_title("AzurSmartMix Control")

        self._build_ops_dialog()

        with ui.header().classes("az-topbar items-center justify-between"):
            with ui.row().classes("items-center gap-3"):
                ui.label("azuracast").classes("az-brand text-xl")
                ui.label("AzurSmartMix Control").classes("az-sub text-sm")
                self._client_sync_badge = ui.html(
                    '<span class="az-badge"><span class="az-dot warn"></span><span>Sync: …</span></span>'
                ).classes("ml-2").props("id=client_sync_badge")
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
                ui.button("Auto JS", on_click=self.enable_autorefresh).props("outline")
                ui.button("Stop Auto", on_click=self.disable_autorefresh).props("outline")

        with ui.element("div").classes("az-wrap"):
            with ui.element("div").classes("az-tabsbar"):
                with ui.tabs(value=self._tab_dashboard, on_change=self._on_main_tab_change).classes(
                    "w-full"
                ) as self._tabs:
                    ui.tab(self._tab_dashboard)
                    ui.tab(self._tab_history)
                    ui.tab(self._tab_library)
                    ui.tab(self._tab_mountpoints)
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

                with ui.tab_panel(self._tab_history):
                    with ui.element("div").classes("az-grid").style("margin-top: 16px;"):
                        self._card_previous()

                with ui.tab_panel(self._tab_library):
                    self._card_library()

                with ui.tab_panel(self._tab_mountpoints):
                    self._card_mountpoints()

                with ui.tab_panel(self._tab_settings):
                    self._card_settings()

        ui.timer(0.1, self.refresh_dashboard, once=True)
        ui.timer(0.12, self.refresh_previous, once=True)
        ui.timer(0.15, self.refresh_library, once=True)
        ui.timer(0.18, self.refresh_mountpoints, once=True)
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
            self.disable_autorefresh()
            await self.refresh_settings()
            return

        if value == self._tab_library:
            self.disable_autorefresh()
            await self.refresh_library()
            return

        if value == self._tab_mountpoints:
            self.disable_autorefresh()
            await self.refresh_mountpoints()
            return

        if value == self._tab_history:
            self.disable_autorefresh()
            await self.refresh_previous()
            return

        self.enable_autorefresh()
        await self.refresh_dashboard()

    async def refresh_visible(self) -> None:
        cur = self._current_main_tab()
        if cur == self._tab_settings:
            await self.refresh_settings()
            return
        if cur == self._tab_library:
            await self.refresh_library()
            return
        if cur == self._tab_mountpoints:
            await self.refresh_mountpoints()
            return
        if cur == self._tab_history:
            await self.refresh_previous()
            return

        try:
            ui.run_javascript("window.azDashboardRefreshNow && window.azDashboardRefreshNow();")
        except Exception:
            pass
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
        try:
            ui.run_javascript("window.azDashboardStart && window.azDashboardStart();")
        except Exception:
            if self._timer is None:
                self._timer = ui.timer(5.0, self._autorefresh_tick)

    def disable_autorefresh(self) -> None:
        try:
            ui.run_javascript("window.azDashboardStop && window.azDashboardStop();")
        except Exception:
            pass
        if self._timer is not None:
            self._timer.cancel()
        self._timer = None
