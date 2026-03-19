from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ContainerInfo:
    name: str
    id: str
    image: str
    status: str
    created_at: Optional[str]
    health: Optional[str]
    started_at: Optional[str]


@dataclass(frozen=True)
class NextEntry:
    ts_raw: str
    ts: Optional[dt.datetime]
    title_raw: str
    title_norm: str
    playlist: str


@dataclass(frozen=True)
class TempoAcceptEntry:
    ts_raw: str
    ts: Optional[dt.datetime]
    a_title: str
    a_norm: str
    b_title: str
    b_norm: str
    delta_pct: Optional[float]
    max_delta_pct: Optional[float]
    attempt: Optional[str]


@dataclass(frozen=True)
class TempoEvent:
    kind: str
    ts_raw: Optional[str]
    ts: Optional[dt.datetime]
    a_title: Optional[str]
    a_norm: str
    b_title: Optional[str]
    b_norm: str
    delta_pct: Optional[float]
    max_delta_pct: Optional[float]
    attempt: Optional[str]
