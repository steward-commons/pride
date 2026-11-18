#!/usr/bin/env python3
"""Shared paths and time helpers for the pride meter.

The live tree is this folder. Tests may redirect data with
PRIDE_DATA so they never touch the live log or state.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Chicago")
TZ_LABEL = "America/Chicago"

CODE_ROOT = Path(__file__).resolve().parent


def data_root() -> Path:
    raw = os.environ.get("PRIDE_DATA")
    return Path(raw).resolve() if raw else CODE_ROOT


def logs_dir() -> Path:
    return data_root() / "logs"


def log_path() -> Path:
    return logs_dir() / "pride.jsonl"


def state_path() -> Path:
    return data_root() / "state.json"


def lock_path() -> Path:
    return logs_dir() / "pride.jsonl.lock"


def now() -> datetime:
    """Current time, or a frozen clock from PRIDE_NOW.

    Tests use the freeze so a snapshot taken under --ts does not
    decay between the earn and the assertion.
    """
    raw = os.environ.get("PRIDE_NOW", "").strip()
    if raw:
        text = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        stamp = datetime.fromisoformat(text)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=TZ)
        return stamp.astimezone(TZ)
    return datetime.now(TZ)


def now_iso() -> str:
    return now().isoformat(timespec="seconds")


def now_human() -> str:
    stamp = now()
    try:
        text = stamp.strftime("%Y-%m-%d %-I:%M %p")
    except ValueError:
        text = stamp.strftime("%Y-%m-%d %I:%M %p").lstrip("0").replace(" 0", " ")
    return f"{text} ({TZ_LABEL})"


def today_key(stamp: datetime | None = None) -> str:
    return (stamp or now()).astimezone(TZ).date().isoformat()
