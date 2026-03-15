from __future__ import annotations

from typing import Any, Dict, List

import html
import uuid

from nicegui import ui


class DashboardMixin:
    # -------------------- Dashboard cards --------------------

    def _card_runtime(self) -> None:
        with ui.element("div").classes("az-card"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Runtime Status")
                self._docker_badge = ui.html(
                    '<span class="az-badge"><span class="az-dot warn"></span><span>Docker: …</span></span>'
                ).props("id=docker_badge")
            with ui.element("div").classes("az-card-b"):
                with ui.element("div").classes("rt-grid"):
                    self._rt_engine_tbl = self._runtime_box("Engine", "rt_engine_tbl")
                    self._rt_sched_tbl = self._runtime_box("Scheduler", "rt_sched_tbl")

    def _runtime_box(self, title: str, html_id: str):
        with ui.element("div").classes("rt-box"):
            ui.label(title).classes("rt-box-h")
            tbl = ui.html(self._runtime_table_html({})).props(f"id={html_id}")
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

    def _card_resources(self) -> None:
        with ui.element("div").classes("az-card"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Resources")
                self._res_host_meta = ui.html('<span class="res-pill">host: …</span>').props("id=res_host_meta")
            with ui.element("div").classes("az-card-b"):
                with ui.element("div").classes("res-shell"):
                    self._res_cpu_html = ui.html(self._resources_cpu_html({})).props("id=res_cpu_html")
                    self._res_mem_html = ui.html(self._resources_mem_html({})).props("id=res_mem_html")

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
        load_txt = (
            f"{l1:.2f} / {l5:.2f}"
            if isinstance(l1, (int, float)) and isinstance(l5, (int, float))
            else "—"
        )
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
                self._now_title = ui.label("—").classes("text-xl").style(
                    "font-weight: 950; margin: 2px 0 0 0;"
                ).props("id=np_title")
                self._now_meta = ui.html(self._now_meta_html({})).props("id=np_meta")
                self._now_player = ui.html(self._player_html(stream_url))
                self._now_sources = ui.label(
                    "Sources: Icecast metadata + engine tempo(select) + scheduler NEXT + engine STREAM_START"
                ).style("opacity:.7; margin-top: 10px;").props("id=np_sources")

    def _now_meta_html(self, now: Dict[str, Any]) -> str:
        playlist_eff = now.get("playlist_effective")
        pl_txt = html.escape(str(playlist_eff)) if playlist_eff else "—"

        predicted = now.get("predicted_next") if isinstance(now.get("predicted_next"), dict) else None
        pred_title = "—"
        pred_pl = "—"
        if predicted:
            pred_title = html.escape(
                str(predicted.get("title_display") or predicted.get("title") or "—")
            )
            pred_pl = html.escape(str(predicted.get("playlist") or "—"))

        ss = now.get("engine_stream_start") if isinstance(now.get("engine_stream_start"), dict) else None
        hint = ""
        if ss and ss.get("ok") and ss.get("recent"):
            age = ss.get("age_s")
            age_txt = f"{age}s" if isinstance(age, int) else "recent"
            hint = (
                f'<span class="np-pill"><span class="t-ok t-bold">STREAM_START</span>'
                f'<span class="t-dim">({html.escape(age_txt)})</span></span>'
            )
        elif ss and ss.get("ok") and ss.get("line"):
            age = ss.get("age_s")
            age_txt = f"{age}s" if isinstance(age, int) else ""
            hint = (
                f'<span class="np-pill"><span class="t-dim">last STREAM_START</span>'
                f'<span class="t-dim">{html.escape(age_txt)}</span></span>'
            )

        return (
            '<div class="np-meta">'
            f'  <div class="np-line"><span class="np-k">playlist:</span> <span class="np-v" data-copy="{pl_txt}">{pl_txt}</span></div>'
            f'  <div class="np-line"><span class="np-k">next(pred):</span> <span class="np-v" data-copy="{pred_title}">{pred_title}</span>'
            f'    <span class="t-dim">|</span> <span class="np-k">pl:</span> <span class="np-v" data-copy="{pred_pl}">{pred_pl}</span></div>'
            f'  <div class="np-line">{hint}</div>'
            "</div>"
        )

    def _player_html(self, url: str) -> str:
        player_id = f"az_stream_{uuid.uuid4().hex}"
        u = html.escape(url)
        return (
            f'<div class="az-stream-player" id="{player_id}" data-stream-url="{u}">'
            f'  <audio class="az-stream-audio" preload="none" crossorigin="anonymous" playsinline></audio>'
            f'  <div class="az-stream-top">'
            f'    <div class="az-stream-live">'
            f'      <span class="az-live-dot"></span>'
            f'      <span>LIVE</span>'
            f'    </div>'
            f'    <div class="az-stream-state" data-role="state">idle</div>'
            f'  </div>'
            f'  <div class="az-stream-controls">'
            f'    <button type="button" class="az-stream-btn primary" onclick="window.azStreamPlay(\'{player_id}\')">Play</button>'
            f'    <button type="button" class="az-stream-btn" onclick="window.azStreamStop(\'{player_id}\')">Stop</button>'
            f'    <button type="button" class="az-stream-btn" onclick="window.azStreamToggleMute(\'{player_id}\')">Mute</button>'
            f'    <div class="az-stream-volume-wrap">'
            f'      <span class="az-stream-vol-label">Vol</span>'
            f'      <input class="az-stream-volume" type="range" min="0" max="100" value="100" '
            f'        oninput="window.azStreamSetVolume(\'{player_id}\', this.value)" />'
            f'    </div>'
            f'  </div>'
            f'  <div class="az-stream-hint" data-copy="{u}">{u}</div>'
            f"</div>"
        )

    def _card_upcoming(self) -> None:
        with ui.element("div").classes("az-card"):
            with ui.element("div").classes("az-card-h"):
                ui.label("Upcoming")
                self._up_source = ui.label("from engine tempo(select) log").classes("text-xs").style(
                    "opacity:.85;"
                ).props("id=up_source")
            with ui.element("div").classes("az-card-b"):
                self._up_list_container = ui.html('<div class="az-list"><div style="opacity:.7;">—</div></div>').props("id=upcoming_list")

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
                        with ui.element("div").classes("console-frame").style(
                            "background: rgba(0,0,0,.55) !important;"
                        ):
                            self._log_html_engine = ui.html('<div class="console-content">—</div>').props("id=log_engine")
                    with ui.tab_panel("scheduler"):
                        with ui.element("div").classes("console-frame").style(
                            "background: rgba(0,0,0,.55) !important;"
                        ):
                            self._log_html_sched = ui.html('<div class="console-content">—</div>').props("id=log_sched")

    def _apply_resources_payload(self, data: Dict[str, Any]) -> None:
        if self._res_host_meta:
            src = html.escape(str(data.get("source") or "host"))
            self._res_host_meta.set_content(f'<span class="res-pill">source: {src}</span>')
        if self._res_cpu_html:
            self._res_cpu_html.set_content(
                self._resources_cpu_html(data if isinstance(data, dict) else {})
            )
        if self._res_mem_html:
            self._res_mem_html.set_content(
                self._resources_mem_html(data if isinstance(data, dict) else {})
            )

    def _apply_runtime_payload(self, rt: Dict[str, Any]) -> None:
        docker_ok = bool(rt.get("docker_ping"))
        self._set_docker_badge(ok=docker_ok, text=f"Docker: {'OK' if docker_ok else 'DOWN'}")

        eng = rt.get("engine") or {}
        sch = rt.get("scheduler") or {}

        if self._rt_engine_tbl:
            self._rt_engine_tbl.set_content(self._runtime_table_html(eng))
        if self._rt_sched_tbl:
            self._rt_sched_tbl.set_content(self._runtime_table_html(sch))

    def _apply_now_payload(self, now: Dict[str, Any]) -> None:
        title = now.get("title_effective") or now.get("title_observed") or "—"
        if self._now_title:
            self._now_title.set_text(title)
        if self._now_meta:
            self._now_meta.set_content(self._now_meta_html(now if isinstance(now, dict) else {}))
        if self._now_sources:
            source_txt = str((now.get("source") or "Icecast metadata + engine tempo(select)")).strip()
            self._now_sources.set_text(f"Sources: {source_txt}")

    def _apply_upcoming_payload(self, up: Dict[str, Any]) -> None:
        items = up.get("upcoming") or []
        if not isinstance(items, list):
            items = []

        if self._up_source:
            src = up.get("source") if isinstance(up, dict) else None
            primary = None
            if isinstance(src, dict):
                primary = src.get("primary")
            self._up_source.set_text(str(primary or "from engine tempo(select) log"))

        if self._up_list_container is None:
            return

        if not items:
            self._up_list_container.set_content('<div class="az-list"><div style="opacity:.7;">—</div></div>')
            return

        rows: List[str] = []
        for i, it in enumerate(items, start=1):
            if not isinstance(it, dict):
                continue
            title = str(it.get("title_display") or it.get("title") or "—")
            playlist = str(it.get("playlist") or "—")
            ts = str(it.get("ts") or "")
            delta_pct = it.get("delta_pct")

            title_e = html.escape(title)
            playlist_e = html.escape(playlist)
            ts_e = html.escape(ts)
            delta_e = (
                html.escape(f"{float(delta_pct):.2f}%")
                if isinstance(delta_pct, (int, float))
                else ""
            )

            parts: List[str] = []
            if playlist and playlist != "—":
                parts.append(
                    f'<span class="t-cyan t-bold" data-copy="{playlist_e}">{playlist_e}</span>'
                )
            if delta_e:
                parts.append(f'<span class="t-dim">Δ</span> <span class="t-ok t-bold">{delta_e}</span>')
            if ts:
                parts.append(f'<span class="t-dim">[{ts_e}]</span>')

            tail = ""
            if parts:
                tail = ' <span class="t-dim">|</span> ' + " ".join(parts)

            rows.append(
                f'<div class="az-item"><span class="idx">{i}.</span> '
                f'<span class="txt" data-copy="{title_e}">{title_e}</span>'
                f'{tail}'
                f"</div>"
            )

        self._up_list_container.set_content('<div class="az-list">' + "".join(rows) + "</div>")

    def _apply_logs_payload(self, engine_text: str, scheduler_text: str) -> None:
        if self._log_html_engine:
            self._log_html_engine.set_content(
                f'<div class="console-content">{html.escape(engine_text)}</div>'
            )
        if self._log_html_sched:
            self._log_html_sched.set_content(
                f'<div class="console-content">{html.escape(scheduler_text)}</div>'
            )

    async def refresh_dashboard(self) -> None:
        try:
            data = await self._get_json("/panel/dashboard?upcoming_n=10&include_logs=true&engine_log_tail=200&scheduler_log_tail=200")
        except Exception:
            await self.refresh_resources()
            await self.refresh_runtime()
            await self.refresh_now()
            await self.refresh_upcoming()
            await self.refresh_logs()
            return

        self._apply_resources_payload(data.get("resources") if isinstance(data, dict) else {})
        self._apply_runtime_payload(data.get("runtime") if isinstance(data, dict) else {})
        self._apply_now_payload(data.get("now") if isinstance(data, dict) else {})
        self._apply_upcoming_payload(data.get("upcoming") if isinstance(data, dict) else {})

        logs = data.get("logs") if isinstance(data, dict) and isinstance(data.get("logs"), dict) else {}
        self._apply_logs_payload(
            str(logs.get("engine") or "—"),
            str(logs.get("scheduler") or "—"),
        )

    async def refresh_resources(self) -> None:
        try:
            data = await self._get_json("/panel/resources")
        except Exception:
            data = {}
        self._apply_resources_payload(data if isinstance(data, dict) else {})

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
        self._apply_runtime_payload(rt if isinstance(rt, dict) else {})

    def _set_docker_badge(self, ok: bool, text: str) -> None:
        if self._docker_badge is None:
            return
        dot = "ok" if ok else "err"
        self._docker_badge.set_content(
            f'<span class="az-badge"><span class="az-dot {dot}"></span><span>{html.escape(text)}</span></span>'
        )

    async def refresh_now(self) -> None:
        try:
            now = await self._get_json("/panel/now")
            self._apply_now_payload(now if isinstance(now, dict) else {})
        except Exception:
            if self._now_title:
                self._now_title.set_text("—")
            if self._now_meta:
                self._now_meta.set_content(self._now_meta_html({}))
            if self._now_sources:
                self._now_sources.set_text("Sources: —")

    async def refresh_upcoming(self) -> None:
        try:
            up = await self._get_json("/panel/upcoming?n=10")
        except Exception:
            up = {}
        self._apply_upcoming_payload(up if isinstance(up, dict) else {})

    async def refresh_logs(self) -> None:
        try:
            eng = await self._get_text("/logs?service=engine&tail=200")
        except Exception:
            eng = "—"

        try:
            sch = await self._get_text("/logs?service=scheduler&tail=200")
        except Exception:
            sch = "—"

        self._apply_logs_payload(eng, sch)
