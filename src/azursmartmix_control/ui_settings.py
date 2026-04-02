# src/azursmartmix_control/ui_settings.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import csv
import html
import os
import re
from copy import deepcopy
from pathlib import Path

from nicegui import ui


class SettingsMixin:
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

    # -------------------- Mountpoints UI --------------------

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
                                        ui.html(
                                            '<span class="az-up-badge runtime">SELECTED</span>' if selected else ""
                                        )
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
                sw = ui.switch(
                    value=bool(current),
                    on_change=lambda e, idx=idx, key=key: self._mountpoint_set_field(idx, key, bool(e.value)),
                ).props("dense").classes("set-ctl")
                _ = sw
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

    def _card_mountpoints_manager(self) -> None:
        self._ensure_mountpoint_state()
        with ui.element("div").classes("az-card").style("grid-column: 1 / -1; min-width: unset; margin-bottom: 16px;"):
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

    # -------------------- Settings tab --------------------

    def _card_settings(self) -> None:
        self._card_mountpoints_manager()

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

    def _build_topcat_tabs(self) -> None:
        if not self._settings_topcat_container:
            return
        topcats = self._topcats_from_csv()
        if self._settings_topcat_value not in topcats:
            self._settings_topcat_value = topcats[0] if topcats else "Main"
        self._settings_topcat_container.clear()
        with self._settings_topcat_container:
            with ui.tabs(value=self._settings_topcat_value, on_change=self._on_topcat_change).classes(
                "w-full"
            ) as t:
                self._settings_topcat_tabs = t
                for tc in topcats:
                    ui.tab(tc)

    def _render_settings_grid(self) -> None:
        if not self._settings_grid_container:
            return

        self._build_topcat_tabs()
        selected_topcat = self._settings_topcat_value or (
            self._topcats_from_csv()[0] if self._topcats_from_csv() else "Main"
        )

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
        await self.refresh_mountpoints()

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
