from __future__ import annotations

import ast
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

from .docker_base import DockerBase
from .docker_models import NextEntry, TempoAcceptEntry, TempoEvent


class DockerLogParsingMixin(DockerBase):
    """Parsing métier des logs engine/scheduler, isolé du runtime Docker."""

    @staticmethod
    def _anchor_index_for_current(events: List[TempoEvent], cur_norm: str) -> Tuple[Optional[int], bool]:
        for i in range(len(events) - 1, -1, -1):
            ev = events[i]
            if not isinstance(ev, TempoEvent) or ev.kind != "accept":
                continue
            if ev.a_norm == cur_norm:
                return i, True
            if ev.b_norm == cur_norm:
                return i + 1, False
        return None, False

    # ----------------------- Tempo selected titles -----------------------

    def extract_tempo_selected_titles(self, engine_container: str, tail: int = 2500) -> Dict[str, Any]:
        txt, lines = self._iter_clean_log_lines(engine_container, tail)
        err = self._ok_or_error(txt, "engine_logs_tempo", "engine_container", engine_container)
        if err:
            return {**err, "titles": []}

        titles: List[str] = []
        for line in lines:
            m_meta = self._RE_TEMPO_SELECT_OK_META.search(line)
            if m_meta:
                try:
                    meta = ast.literal_eval((m_meta.group("meta") or "").strip())
                except Exception:
                    meta = None
                if isinstance(meta, dict):
                    t = self._coerce_rel_title(str(meta.get("b_rel") or ""))
                    if t:
                        titles.append(t)
                        continue

            m_rel = self._RE_TEMPO_SELECT_OK_REL.search(line)
            if m_rel:
                t = self._coerce_rel_title(m_rel.group("rel") or "")
                if t:
                    titles.append(t)

        return {
            "ok": True,
            "source": "engine_logs_tempo",
            "engine_container": engine_container,
            "titles": titles,
            "count": len(titles),
        }

    # ----------------------- Tempo runtime state -----------------------

    def extract_tempo_runtime_state(self, engine_container: str, tail: int = 2500) -> Dict[str, Any]:
        txt, lines = self._iter_clean_log_lines(engine_container, tail)
        err = self._ok_or_error(txt, "engine_logs_tempo_runtime", "engine_container", engine_container)
        if err:
            return {
                **err,
                "current_title": None,
                "next_title": None,
                "current_bpm": None,
                "next_bpm": None,
                "playback_stage": None,
                "playback_uri": None,
                "playback_title": None,
            }

        last_state: Optional[Dict[str, Any]] = None
        last_state_idx = -1
        last_playback: Optional[Dict[str, Any]] = None
        last_playback_idx = -1

        for idx, line in enumerate(lines):
            m_any = self._RE_TEMPO_SELECT_ANY_META.search(line)
            if m_any:
                try:
                    meta = ast.literal_eval((m_any.group("meta") or "").strip())
                except Exception:
                    meta = None

                if isinstance(meta, dict):
                    last_state = {
                        "ok": True,
                        "source": "engine_logs_tempo_runtime",
                        "engine_container": engine_container,
                        "decision_ok": str(m_any.group("ok") or "").lower() == "true",
                        "fail_open": False,
                        "current_title": self._coerce_rel_title(str(meta.get("a_rel") or "")),
                        "next_title": self._coerce_rel_title(str(meta.get("b_rel") or "")),
                        "current_bpm": self._bpm_or_none(meta.get("a")),
                        "next_bpm": self._bpm_or_none(meta.get("b")),
                        "a_src": meta.get("a_src"),
                        "b_src": meta.get("b_src"),
                        "a_fx": meta.get("a_fx"),
                        "b_fx": meta.get("b_fx"),
                        "a_tid": meta.get("a_tid"),
                        "b_tid": meta.get("b_tid"),
                        "raw_meta": meta,
                    }
                    last_state_idx = idx
                    continue

            if self._RE_TEMPO_EXHAUST_FAIL_OPEN.search(line):
                if last_state:
                    last_state["fail_open"] = True
                    last_state["decision_ok"] = True
                continue

            m_uri = self._RE_AFT_SET_URI.search(line)
            if m_uri:
                last_playback = self._playback_state_from_uri(m_uri.group("uri") or "")
                last_playback["aft"] = int(m_uri.group("aft"))
                last_playback_idx = idx

        if last_state is None:
            return {
                "ok": False,
                "source": "engine_logs_tempo_runtime",
                "engine_container": engine_container,
                "error": "no tempo(select) state found in logs",
                "current_title": None,
                "next_title": None,
                "current_bpm": None,
                "next_bpm": None,
                "playback_stage": (last_playback or {}).get("playback_stage"),
                "playback_uri": (last_playback or {}).get("playback_uri"),
                "playback_title": (last_playback or {}).get("playback_title"),
            }

        merged = dict(last_state)
        playback = last_playback if last_playback and last_playback_idx >= last_state_idx else {}
        merged.update(
            {
                "playback_stage": playback.get("playback_stage"),
                "playback_uri": playback.get("playback_uri"),
                "playback_path": playback.get("playback_path"),
                "playback_title": playback.get("playback_title"),
                "playback_pack_id": playback.get("pack_id"),
                "playback_aft": playback.get("aft"),
            }
        )
        return merged

    # ----------------------- Tempo event stream -----------------------

    def extract_tempo_event_stream(self, engine_container: str, tail: int = 3000) -> Dict[str, Any]:
        txt, lines = self._iter_clean_log_lines(engine_container, tail)
        err = self._ok_or_error(txt, "engine_logs_tempo_event_stream", "engine_container", engine_container)
        if err:
            return {**err, "events": []}

        events: List[TempoEvent] = []

        for line in lines:
            ts_raw = self._extract_log_ts_raw(line)
            ts = self._parse_sched_ts(ts_raw) if ts_raw else None

            m_meta = self._RE_TEMPO_SELECT_OK_META.search(line)
            if m_meta:
                try:
                    meta = ast.literal_eval((m_meta.group("meta") or "").strip())
                except Exception:
                    meta = None

                if isinstance(meta, dict):
                    a_title = self._coerce_rel_title(str(meta.get("a_rel") or ""))
                    b_title = self._coerce_rel_title(str(meta.get("b_rel") or ""))
                    if a_title and b_title:
                        events.append(
                            TempoEvent(
                                kind="accept",
                                ts_raw=ts_raw,
                                ts=ts,
                                a_title=a_title,
                                a_norm=self.normalize_title(a_title),
                                b_title=b_title,
                                b_norm=self.normalize_title(b_title),
                                delta_pct=self._extract_float_from_line(self._RE_DELTA_PCT, line),
                                max_delta_pct=self._extract_float_from_line(self._RE_MAX_DELTA_PCT, line),
                                attempt=self._extract_attempt_from_line(line),
                            )
                        )
                        continue

            if self._RE_TEMPO_EXHAUST_FAIL_OPEN.search(line):
                events.append(
                    TempoEvent(
                        kind="fail_open",
                        ts_raw=ts_raw,
                        ts=ts,
                        a_title=None,
                        a_norm="",
                        b_title=None,
                        b_norm="",
                        delta_pct=None,
                        max_delta_pct=None,
                        attempt=None,
                    )
                )

        return {
            "ok": True,
            "source": "engine_logs_tempo_event_stream",
            "engine_container": engine_container,
            "count": len(events),
            "events": events,
        }

    def extract_tempo_accept_entries(self, engine_container: str, tail: int = 3000) -> Dict[str, Any]:
        data = self.extract_tempo_event_stream(engine_container, tail=tail)
        if not data.get("ok"):
            return {
                "ok": False,
                "source": "engine_logs_tempo_accept",
                "engine_container": engine_container,
                "error": data.get("error"),
                "entries": [],
            }

        entries: List[TempoAcceptEntry] = []
        for ev in data.get("events") or []:
            if not isinstance(ev, TempoEvent) or ev.kind != "accept":
                continue
            entries.append(
                TempoAcceptEntry(
                    ts_raw=ev.ts_raw or "",
                    ts=ev.ts,
                    a_title=ev.a_title or "",
                    a_norm=ev.a_norm,
                    b_title=ev.b_title or "",
                    b_norm=ev.b_norm,
                    delta_pct=ev.delta_pct,
                    max_delta_pct=ev.max_delta_pct,
                    attempt=ev.attempt,
                )
            )

        return {
            "ok": True,
            "source": "engine_logs_tempo_accept",
            "engine_container": engine_container,
            "count": len(entries),
            "entries": [
                {
                    "ts": e.ts_raw,
                    "a_title": e.a_title,
                    "a_norm": e.a_norm,
                    "b_title": e.b_title,
                    "b_norm": e.b_norm,
                    "delta_pct": e.delta_pct,
                    "max_delta_pct": e.max_delta_pct,
                    "attempt": e.attempt,
                }
                for e in entries
            ],
        }

    def compute_upcoming_from_tempo_accepts(
        self,
        engine_container: str,
        current_title: Optional[str],
        n: int = 10,
        tail: int = 3000,
    ) -> Dict[str, Any]:
        cur_norm = self.normalize_title(current_title or "")
        data = self.extract_tempo_event_stream(engine_container, tail=tail)
        if not data.get("ok"):
            return {
                "ok": False,
                "error": data.get("error"),
                "upcoming": [],
                "source": "engine_logs_tempo_accept",
            }

        events = data.get("events") or []
        if not events:
            return {
                "ok": False,
                "error": "no tempo events found",
                "upcoming": [],
                "source": "engine_logs_tempo_accept",
            }

        if not cur_norm:
            return {
                "ok": True,
                "source": "engine_logs_tempo_accept_waiting_for_current",
                "current_title_found": False,
                "current_title": current_title,
                "upcoming": [],
                "entries_considered": 0,
                "barrier_hit": False,
            }

        anchor_idx, _include_anchor = self._anchor_index_for_current(events, cur_norm)
        if anchor_idx is None:
            return {
                "ok": True,
                "source": "engine_logs_tempo_accept_unanchored",
                "current_title_found": False,
                "current_title": current_title,
                "upcoming": [],
                "entries_considered": 0,
                "barrier_hit": False,
            }

        seen: set[str] = set()
        out: List[Dict[str, Any]] = []
        entries_considered = 0
        barrier_hit = False

        for ev in events[anchor_idx:]:
            if not isinstance(ev, TempoEvent):
                continue

            if ev.kind == "fail_open":
                barrier_hit = True
                break

            if ev.kind != "accept":
                continue

            entries_considered += 1

            if ev.a_norm != cur_norm and not out:
                # Garde-fou de continuité pour ne pas afficher une chaîne orpheline.
                continue

            b_norm = ev.b_norm.strip()
            if not b_norm or b_norm == cur_norm or b_norm in seen:
                cur_norm = b_norm or cur_norm
                continue

            seen.add(b_norm)
            out.append(
                {
                    "title": ev.b_title,
                    "title_display": self.display_title(str(ev.b_title or "")),
                    "playlist": None,
                    "ts": ev.ts_raw,
                    "from_title": ev.a_title,
                    "delta_pct": ev.delta_pct,
                    "max_delta_pct": ev.max_delta_pct,
                    "attempt": ev.attempt,
                }
            )
            cur_norm = b_norm

            if len(out) >= n:
                break

        return {
            "ok": True,
            "source": "engine_logs_tempo_accept_after_current",
            "current_title_found": True,
            "current_title": current_title,
            "upcoming": out,
            "entries_considered": entries_considered,
            "barrier_hit": barrier_hit,
        }

    # ----------------------- Preprocess fallback -----------------------

    def extract_preprocess_titles(self, engine_container: str, tail: int = 2500) -> Dict[str, Any]:
        txt, lines = self._iter_clean_log_lines(engine_container, tail)
        err = self._ok_or_error(txt, "engine_logs", "engine_container", engine_container)
        if err:
            return {**err, "titles": []}

        titles: List[str] = []
        for line in lines:
            m = self._RE_PREPROCESS.search(line)
            if not m:
                continue
            t = self._clean_preprocess_title((m.group("rest") or "").strip())
            if t:
                titles.append(t)

        return {
            "ok": True,
            "source": "engine_logs",
            "engine_container": engine_container,
            "titles": titles,
            "count": len(titles),
        }

    def compute_upcoming_from_preprocess(
        self,
        engine_container: str,
        current_title: Optional[str],
        n: int = 10,
        tail: int = 2500,
    ) -> Dict[str, Any]:
        cur_norm = self.normalize_title(current_title or "")

        tempo_data = self.extract_tempo_selected_titles(engine_container, tail=tail)
        if tempo_data.get("ok"):
            tempo_titles = [t for t in (tempo_data.get("titles") or []) if isinstance(t, str) and t.strip()]
            if tempo_titles:
                items = [
                    {
                        "title": t,
                        "title_display": self.display_title(t),
                        "title_norm": self.normalize_title(t),
                        "playlist": None,
                        "ts": None,
                    }
                    for t in tempo_titles
                ]
                out = self._slice_from_current(
                    items=items,
                    current_norm=cur_norm,
                    norm_key="title_norm",
                    n=n,
                    fallback_mult=4,
                    source_after="engine_logs_tempo_after_current",
                    source_fallback="engine_logs_tempo_fallback_tail",
                    current_title=current_title,
                )
                out["upcoming"] = [e["title_display"] for e in out["upcoming"]]
                return out

        data = self.extract_preprocess_titles(engine_container, tail=tail)
        if not data.get("ok"):
            return {"ok": False, "error": data.get("error"), "upcoming": [], "source": "engine_logs"}

        titles = [t for t in (data.get("titles") or []) if isinstance(t, str) and t.strip()]
        if not titles:
            return {"ok": False, "error": "no preprocess titles found", "upcoming": [], "source": "engine_logs"}

        items = [
            {
                "title": t,
                "title_display": self.display_title(t),
                "title_norm": self.normalize_title(t),
                "playlist": None,
                "ts": None,
            }
            for t in self._dedupe_keep_order(titles)
        ]
        out = self._slice_from_current(
            items=items,
            current_norm=cur_norm,
            norm_key="title_norm",
            n=n,
            fallback_mult=4,
            source_after="engine_logs_preprocess_after_current",
            source_fallback="engine_logs_preprocess_fallback_tail",
            current_title=current_title,
        )
        out["upcoming"] = [e["title_display"] for e in out["upcoming"]]
        return out

    # ----------------------- Scheduler NEXT -----------------------

    def extract_scheduler_next_entries(self, scheduler_container: str, tail: int = 2500) -> Dict[str, Any]:
        txt, lines = self._iter_clean_log_lines(scheduler_container, tail)
        err = self._ok_or_error(txt, "scheduler_logs", "scheduler_container", scheduler_container)
        if err:
            return {**err, "entries": []}

        entries: List[NextEntry] = []
        for line in lines:
            m = self._RE_SCHED_NEXT.search(line)
            if not m:
                continue

            ts_raw = m.group("ts") or ""
            title_raw = m.group("title") or ""
            playlist = m.group("playlist") or ""
            entries.append(
                NextEntry(
                    ts_raw=ts_raw,
                    ts=self._parse_sched_ts(ts_raw),
                    title_raw=title_raw,
                    title_norm=self.normalize_title(title_raw),
                    playlist=playlist,
                )
            )

        return {
            "ok": True,
            "source": "scheduler_logs",
            "scheduler_container": scheduler_container,
            "count": len(entries),
            "entries": [
                {
                    "ts": e.ts_raw,
                    "title": e.title_raw,
                    "title_norm": e.title_norm,
                    "title_display": self.display_title(e.title_raw),
                    "playlist": e.playlist,
                }
                for e in entries
            ],
        }

    def infer_playlist_for_title_from_scheduler(
        self,
        scheduler_container: str,
        current_title: Optional[str],
        tail: int = 2500,
    ) -> Dict[str, Any]:
        cur_norm = self.normalize_title(current_title or "")
        data = self.extract_scheduler_next_entries(scheduler_container, tail=tail)
        if not data.get("ok"):
            return {"ok": False, "error": data.get("error"), "playlist": None, "match": None}

        entries = data.get("entries") or []
        if not cur_norm or not entries:
            return {
                "ok": True,
                "playlist": None,
                "match": None,
                "current_title": current_title,
                "current_norm": cur_norm,
            }

        match = next((e for e in reversed(entries) if (e.get("title_norm") or "") == cur_norm), None)
        if not match:
            return {
                "ok": True,
                "playlist": None,
                "match": None,
                "current_title": current_title,
                "current_norm": cur_norm,
            }

        return {
            "ok": True,
            "playlist": match.get("playlist"),
            "match": match,
            "current_title": current_title,
            "current_norm": cur_norm,
        }

    def compute_upcoming_from_scheduler_next(
        self,
        scheduler_container: str,
        current_title: Optional[str],
        n: int = 10,
        tail: int = 2500,
    ) -> Dict[str, Any]:
        cur_norm = self.normalize_title(current_title or "")
        data = self.extract_scheduler_next_entries(scheduler_container, tail=tail)
        if not data.get("ok"):
            return {"ok": False, "error": data.get("error"), "upcoming": [], "source": "scheduler_logs"}

        raw_entries = data.get("entries") or []
        if not raw_entries:
            return {
                "ok": False,
                "error": "no scheduler NEXT entries found",
                "upcoming": [],
                "source": "scheduler_logs",
            }

        items = [
            {
                "title": e.get("title"),
                "title_display": e.get("title_display") or self.display_title(str(e.get("title") or "")),
                "title_norm": e.get("title_norm"),
                "playlist": e.get("playlist"),
                "ts": e.get("ts"),
            }
            for e in raw_entries
        ]

        return self._slice_from_current(
            items=items,
            current_norm=cur_norm,
            norm_key="title_norm",
            n=n,
            fallback_mult=8,
            source_after="scheduler_logs_after_current",
            source_fallback="scheduler_logs_fallback_tail",
            current_title=current_title,
        )

    # ----------------------- STREAM_START -----------------------

    def last_engine_stream_start(
        self,
        engine_container: str,
        tail: int = 800,
        recent_window_s: int = 10,
    ) -> Dict[str, Any]:
        txt, lines = self._iter_clean_log_lines(engine_container, tail)
        err = self._ok_or_error(txt, "engine_logs", "engine_container", engine_container)
        if err:
            return {**err, "line": None, "recent": False}

        last_line = None
        last_ts: Optional[dt.datetime] = None

        for line in lines:
            if not self._RE_STREAM_START.search(line):
                continue
            last_line = line.strip()
            ts_raw = self._extract_log_ts_raw(last_line)
            last_ts = self._parse_sched_ts(ts_raw) if ts_raw else None

        if not last_line:
            return {
                "ok": True,
                "source": "engine_logs",
                "engine_container": engine_container,
                "line": None,
                "recent": False,
            }

        recent = False
        age_s = None
        if last_ts:
            try:
                now_local = dt.datetime.now()
                age_s = int((now_local - last_ts).total_seconds())
                recent = age_s >= 0 and age_s <= int(recent_window_s)
            except Exception:
                recent = False

        return {
            "ok": True,
            "source": "engine_logs",
            "engine_container": engine_container,
            "line": last_line,
            "ts": last_ts.isoformat() if last_ts else None,
            "age_s": age_s,
            "recent": recent,
            "recent_window_s": int(recent_window_s),
        }
