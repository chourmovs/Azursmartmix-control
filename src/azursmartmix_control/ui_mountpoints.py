from __future__ import annotations

from typing import Any, Dict, List, Tuple

import html
from copy import deepcopy

from nicegui import ui


class MountpointsMixin:
    def _ensure_mountpoint_state(self) -> None:
        if not hasattr(self, "_mount_cfg_base"):
            self._mount_cfg_base = []
        if not hasattr(self, "_mount_cfg_work"):
            self._mount_cfg_work = []
        if not hasattr(self, "_mount_cfg_selected_idx"):
            self._mount_cfg_selected_idx = None
        if not hasattr(self, "_mount_cfg_busy"):
            self._mount_cfg_busy = False
        if not hasattr(self, "_mount_cfg_list_container"):
            self._mount_cfg_list_container = None
        if not hasattr(self, "_mount_cfg_editor_container"):
            self._mount_cfg_editor_container = None
        if not hasattr(self, "_mount_cfg_meta"):
            self._mount_cfg_meta = None

    def _mountpoint_common_fields(self) -> List[Tuple[str, str, str]]:
        return [
            ("name", "Internal name", "text"),
            ("type", "Type", "text"),
            ("host", "Host", "text"),
            ("port", "Port", "int"),
            ("mount", "Mount path", "text"),
            ("username", "Username", "text"),
            ("password", "Password", "text"),
            ("public", "Public", "bool"),
            ("stream_name", "Stream name", "text"),
            ("description", "Description", "text"),
            ("genre", "Genre", "text"),
            ("format", "Format", "text"),
            ("bitrate_kbps", "Bitrate kbps", "int"),
            ("cbr", "CBR", "bool"),
            ("sample_rate", "Sample rate", "int"),
            ("channels", "Channels", "int"),
            ("send_title_info", "Send title info", "bool"),
            ("protocol", "Protocol", "int"),
        ]

    def _mountpoint_default_item(self) -> Dict[str, Any]:
        idx = len(self._mount_cfg_work or []) + 1
        return {
            "name": f"azuramix_mount_{idx}",
            "type": "icecast",
            "host": "web",
            "port": 8000,
            "mount": f"/azuramix_{idx}.mp3",
            "username": "source",
            "password": "",
            "public": False,
            "stream_name": f"AzurMix Mount {idx}",
            "description": "AutoDJ replacement via AzuraMix",
            "genre": "",
            "format": "mp3",
            "bitrate_kbps": 128,
            "cbr": True,
            "sample_rate": 44100,
            "channels": 2,
            "send_title_info": True,
            "protocol": 3,
        }

    def _mountpoint_display_name(self, item: Dict[str, Any], idx: int) -> str:
        if not isinstance(item, dict):
            return f"Mount {idx + 1}"
        name = str(item.get("name") or "").strip()
        mount = str(item.get("mount") or "").strip()
        fmt = str(item.get("format") or "").strip()
        if name and mount:
            return f"{name} • {mount}"
        if name:
            return name
        if mount:
            return mount
        if fmt:
            return f"Mount {idx + 1} • {fmt}"
        return f"Mount {idx + 1}"

    def _mountpoint_set_field(self, idx: int, key: str, value: Any) -> None:
        if idx < 0 or idx >= len(self._mount_cfg_work):
            return
        item = self._mount_cfg_work[idx]
        if not isinstance(item, dict):
            return
        item[str(key)] = value
        self._render_mountpoint_list()

    def _render_mountpoint_list(self) -> None:
        self._ensure_mountpoint_state()
        if not self._mount_cfg_list_container:
            return

        self._mount_cfg_list_container.clear()
        items = self._mount_cfg_work or []

        with self._mount_cfg_list_container:
            if not items:
                ui.html('<div class="az-list"><div class="az-item"><span class="txt">No mountpoints configured.</span></div></div>')
                return

            for idx, item in enumerate(items):
                selected = idx == self._mount_cfg_selected_idx
                fmt = html.escape(str(item.get("format") or "—"))
                bitrate = html.escape(str(item.get("bitrate_kbps") if item.get("bitrate_kbps") not in (None, "") else "—"))
                mount = html.escape(str(item.get("mount") or "—"))

                with ui.element("div").classes("az-item"):
                    with ui.element("div").classes("az-up-item"):
                        with ui.element("div").classes("az-up-head"):
                            with ui.element("div").classes("az-up-main"):
                                row = ui.row().classes("items-center justify-between w-full")
                                with row:
                                    btn = ui.button(
                                        self._mountpoint_display_name(item, idx),
                                        on_click=lambda _e=None, idx=idx: self._select_mountpoint(idx),
                                    ).props("flat no-caps")
                                    btn.classes("text-left")
                                    btn.style(
                                        "font-weight: 850; justify-content:flex-start; padding:0; min-height:auto; "
                                        + ("color: var(--az-cyan);" if selected else "color: rgba(255,255,255,.96);")
                                    )
                                    with ui.row().classes("items-center gap-2"):
                                        if selected:
                                            ui.html('<span class="az-up-badge runtime">SELECTED</span>')
                                ui.html(
                                    '<div class="az-up-meta">'
                                    f'<span class="az-up-chip playlist"><span>MOUNT</span><span data-copy="{mount}">{mount}</span></span>'
                                    f'<span class="az-up-chip"><span>FMT</span><span data-copy="{fmt}">{fmt}</span></span>'
                                    f'<span class="az-up-chip bpm"><span>KBPS</span><span data-copy="{bitrate}">{bitrate}</span></span>'
                                    '</div>'
                                )

    def _render_mountpoint_editor(self) -> None:
        self._ensure_mountpoint_state()
        if not self._mount_cfg_editor_container:
            return

        self._mount_cfg_editor_container.clear()
        idx = self._mount_cfg_selected_idx
        items = self._mount_cfg_work or []

        with self._mount_cfg_editor_container:
            if idx is None or idx < 0 or idx >= len(items):
                ui.html('<div class="az-list"><div class="az-item"><span class="txt">Select a mountpoint to edit it.</span></div></div>')
                return

            item = items[idx]
            if not isinstance(item, dict):
                ui.html('<div class="az-list"><div class="az-item"><span class="txt">Invalid mountpoint payload.</span></div></div>')
                return

            known_fields = self._mountpoint_common_fields()
            known_keys = {k for k, _label, _kind in known_fields}

            with ui.element("div").classes("set-box"):
                with ui.element("div").classes("set-box-h"):
                    ui.label(self._mountpoint_display_name(item, idx))
                    ui.label(f"Mount #{idx + 1}").classes("meta")

                with ui.element("div").classes("set-box-b"):
                    for key, label, kind in known_fields:
                        cur = item.get(key, "")
                        self._render_mountpoint_field_row(idx, key, label, kind, cur)

                    extra_keys = sorted([k for k in item.keys() if k not in known_keys])
                    for key in extra_keys:
                        self._render_mountpoint_field_row(idx, key, key, "text", item.get(key, ""))

    def _render_mountpoint_field_row(self, idx: int, key: str, label: str, kind: str, value: Any) -> None:
        label_e = html.escape(str(label))
        key_e = html.escape(str(key))

        with ui.element("div").classes("set-row"):
            with ui.element("div").classes("set-left"):
                ui.html(f'<div class="set-name" title="{key_e}" data-copy="{key_e}">{label_e}</div>')
                ui.html(f'<div class="set-desc">config.outputs[].{key_e}</div>')

            if kind == "bool":
                current = bool(value) if isinstance(value, bool) else self._parse_bool_like_key(key, value)
                ui.switch(
                    value=bool(current),
                    on_change=lambda e, idx=idx, key=key: self._mountpoint_set_field(idx, key, bool(e.value)),
                ).props("dense").classes("set-ctl")
                return

            inp = ui.input(
                value="" if value is None else str(value),
                placeholder=label,
                on_change=lambda e, idx=idx, key=key, kind=kind: self._mountpoint_set_field(
                    idx,
                    key,
                    self._mountpoint_cast_value(kind, e.value),
                ),
            ).classes("az-inp").props("dense outlined dark")
            if kind == "int":
                inp.props("type=number")
            inp.classes("set-ctl")

    def _mountpoint_cast_value(self, kind: str, value: Any) -> Any:
        if kind == "int":
            s = str(value or "").strip()
            if not s:
                return ""
            try:
                return int(float(s))
            except Exception:
                return s
        return "" if value is None else str(value)

    def _select_mountpoint(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._mount_cfg_work or []):
            self._mount_cfg_selected_idx = None
        else:
            self._mount_cfg_selected_idx = idx
        self._render_mountpoint_list()
        self._render_mountpoint_editor()

    def _add_mountpoint(self) -> None:
        self._ensure_mountpoint_state()
        self._mount_cfg_work.append(self._mountpoint_default_item())
        self._mount_cfg_selected_idx = len(self._mount_cfg_work) - 1
        self._render_mountpoint_list()
        self._render_mountpoint_editor()

    def _delete_selected_mountpoint(self) -> None:
        self._ensure_mountpoint_state()
        idx = self._mount_cfg_selected_idx
        if idx is None or idx < 0 or idx >= len(self._mount_cfg_work or []):
            ui.notify("No mountpoint selected", type="warning")
            return
        del self._mount_cfg_work[idx]
        if not self._mount_cfg_work:
            self._mount_cfg_selected_idx = None
        else:
            self._mount_cfg_selected_idx = min(idx, len(self._mount_cfg_work) - 1)
        self._render_mountpoint_list()
        self._render_mountpoint_editor()

    def _mountpoints_payload(self) -> List[Dict[str, Any]]:
        return [deepcopy(x) for x in (self._mount_cfg_work or []) if isinstance(x, dict)]

    def _card_mountpoints(self) -> None:
        self._ensure_mountpoint_state()
        with ui.element("div").classes("az-card").style("grid-column: 1 / -1; min-width: unset;"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Mountpoints")
                self._mount_cfg_meta = ui.label("config.yml • outputs[]").classes("text-xs").style("opacity:.85;")

            with ui.element("div").classes("az-card-b"):
                with ui.row().classes("items-center justify-between w-full").style("margin-bottom: 10px; gap: 10px;"):
                    ui.label(
                        "Manage stream outputs from config.yml (outputs[]). Add, edit, delete, then save the whole outputs list."
                    ).style("opacity:.78;")
                    with ui.row().classes("items-center gap-2"):
                        ui.button("Reload mounts", on_click=self.refresh_mountpoints).props("outline")
                        ui.button("Add mount", on_click=self._add_mountpoint).props("outline")
                        ui.button("Delete selected", on_click=self._delete_selected_mountpoint).props("outline color=negative")
                        ui.button("Save mounts", on_click=self.save_mountpoints).props("unelevated color=positive")

                with ui.element("div").classes("az-grid"):
                    with ui.element("div").classes("az-card"):
                        with ui.element("div").classes("az-card-h"):
                            ui.label("Configured outputs")
                        with ui.element("div").classes("az-card-b"):
                            self._mount_cfg_list_container = ui.column().classes("w-full")

                    with ui.element("div").classes("az-card"):
                        with ui.element("div").classes("az-card-h"):
                            ui.label("Selected output")
                        with ui.element("div").classes("az-card-b"):
                            self._mount_cfg_editor_container = ui.column().classes("w-full")

        self._render_mountpoint_list()
        self._render_mountpoint_editor()

    async def refresh_mountpoints(self) -> None:
        self._ensure_mountpoint_state()
        try:
            data = await self._get_json("/config/mountpoints")
            outputs = data.get("outputs") if isinstance(data, dict) else None
            if not isinstance(outputs, list):
                outputs = []

            clean: List[Dict[str, Any]] = []
            for item in outputs:
                if isinstance(item, dict):
                    clean.append(deepcopy(item))

            self._mount_cfg_base = deepcopy(clean)
            self._mount_cfg_work = deepcopy(clean)

            if self._mount_cfg_work:
                if self._mount_cfg_selected_idx is None or self._mount_cfg_selected_idx >= len(self._mount_cfg_work):
                    self._mount_cfg_selected_idx = 0
            else:
                self._mount_cfg_selected_idx = None

            if self._mount_cfg_meta:
                config_file = str(data.get("config_file") or getattr(self.settings, "azuramix_config_file", "config.yml"))
                self._mount_cfg_meta.set_text(f"{config_file} • {len(self._mount_cfg_work)} mount(s)")

            self._render_mountpoint_list()
            self._render_mountpoint_editor()
        except Exception as e:
            if self._mount_cfg_meta:
                self._mount_cfg_meta.set_text(f"config.yml error: {e}")
            self._mount_cfg_base = []
            self._mount_cfg_work = []
            self._mount_cfg_selected_idx = None
            self._render_mountpoint_list()
            self._render_mountpoint_editor()

    async def save_mountpoints(self) -> None:
        self._ensure_mountpoint_state()
        if self._mount_cfg_busy:
            ui.notify("Mountpoints save busy", type="warning")
            return

        self._mount_cfg_busy = True
        try:
            payload = {"outputs": self._mountpoints_payload()}
            r = await self._post_json("/config/mountpoints", payload)
            if r.get("ok"):
                self._set_restart_needed(True)
                ui.notify("Mountpoints saved. Restart/Recreate required.", type="warning")
                await self.refresh_mountpoints()
            else:
                ui.notify(str(r.get("error") or "Mountpoints save failed"), type="negative")
        except Exception as e:
            ui.notify(f"Mountpoints save error: {e}", type="negative")
        finally:
            self._mount_cfg_busy = False
