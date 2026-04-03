from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import csv
import html
import os
import re
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
