#!/usr/bin/env python3
"""Append-only pride log.

The JSONL file is the source of truth. This module only appends or reads.
There is no rewrite, edit, delete, or truncate API. Each record carries
the SHA-256 of the previous raw line so a mid-file edit can be spotted.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import uuid
from pathlib import Path
from collections.abc import Sequence as SequenceLike
from typing import Any, Mapping

import meter
import paths

GENESIS_HASH = "genesis"


class LogError(meter.PrideError):
    """Pride log could not be read or verified."""


class LogTampered(LogError):
    """The append-only chain does not verify."""


def line_hash(raw_line: str) -> str:
    return hashlib.sha256(raw_line.encode("utf-8")).hexdigest()


def _read_raw_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    if not text:
        return []
    # Keep a record of a missing trailing newline so we can still parse,
    # but a well-formed log always ends with a newline from append().
    return text.splitlines()


def read_events(log_file: Path | None = None) -> list[dict[str, Any]]:
    path = log_file or paths.log_path()
    events: list[dict[str, Any]] = []
    for raw in _read_raw_lines(path):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LogError(f"Pride log has a bad JSON line in {path}: {exc}") from exc
        if not isinstance(record, dict):
            raise LogError(f"Pride log line is not an object: {path}")
        events.append(record)
    return events


def verify_chain(log_file: Path | None = None) -> None:
    path = log_file or paths.log_path()
    prev = GENESIS_HASH
    for index, raw in enumerate(_read_raw_lines(path), start=1):
        if not raw.strip():
            raise LogTampered(f"Blank line in pride log at line {index}.")
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LogTampered(f"Pride log line {index} is not JSON: {exc}") from exc
        if not isinstance(record, dict):
            raise LogTampered(f"Pride log line {index} is not an object.")
        claimed = str(record.get("prev_hash") or "")
        if claimed != prev:
            raise LogTampered(
                f"Pride log chain break at line {index}: "
                f"expected prev_hash {prev[:12]}…, found {claimed[:12] or '(missing)'}…"
            )
        expected_seq = index
        seq = record.get("seq")
        if seq is not None and int(seq) != expected_seq:
            raise LogTampered(
                f"Pride log sequence break at line {index}: expected seq {expected_seq}, found {seq}."
            )
        prev = line_hash(raw)


def _tail_state(path: Path) -> tuple[str, int]:
    lines = [line for line in _read_raw_lines(path) if line.strip()]
    if not lines:
        return GENESIS_HASH, 0
    return line_hash(lines[-1]), len(lines)


def append(
    record: Mapping[str, Any],
    log_file: Path | None = None,
    *,
    now_iso: str | None = None,
) -> dict[str, Any]:
    """Append one record. Never rewrites existing bytes."""
    path = log_file or paths.log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = paths.lock_path() if log_file is None else path.with_suffix(path.suffix + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)

    payload = dict(record)
    if "id" not in payload or not payload["id"]:
        payload["id"] = uuid.uuid4().hex[:12]
    if "ts" not in payload or not payload["ts"]:
        payload["ts"] = now_iso or paths.now_iso()

    with open(lock, "a", encoding="utf-8") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        try:
            verify_chain(path)
            prev_hash, count = _tail_state(path)
            payload["prev_hash"] = prev_hash
            payload["seq"] = count + 1
            line = json.dumps(
                payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            )
            # Open append-only. Do not truncate, do not seek backward.
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        finally:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)
    return payload


def snapshot_state(snapshot: meter.Snapshot, state_file: Path | None = None) -> Path:
    """Write a derived cache of the current meter. The log still wins."""
    path = state_file or paths.state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "level": round(snapshot.level, 4),
        "careful": snapshot.careful,
        "rest": snapshot.rest,
        "half_life_days": snapshot.half_life_days,
        "as_of": snapshot.as_of,
        "as_of_human": snapshot.as_of_human,
        "rise_used_today": snapshot.rise_used_today,
        "rise_cap": snapshot.rise_cap,
        "event_count": snapshot.event_count,
        "source": "derived from logs/pride.jsonl; the log is the source of truth",
        "timezone": paths.TZ_LABEL,
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def format_log(events: SequenceLike | None = None, *, limit: int = 0) -> str:
    records = list(events) if events is not None else read_events()
    if limit and limit > 0:
        records = records[-limit:]
    lines = [
        "Pride log (America/Chicago). Append-only. The log is the source of truth.",
        "",
    ]
    if not records:
        lines.append("(empty)")
        return "\n".join(lines)
    for event in records:
        ts = str(event.get("ts") or "")
        try:
            human = _human_ts(ts)
        except ValueError:
            human = ts or "(no timestamp)"
        action = str(event.get("action") or "").upper()
        typ = str(event.get("type") or "")
        applied = event.get("applied_weight")
        try:
            weight_text = f"{float(applied):+.2f}"
        except (TypeError, ValueError):
            weight_text = str(applied)
        cap = "  [capped]" if event.get("capped") else ""
        reason = str(event.get("reason") or "")
        evidence = event.get("evidence") if isinstance(event.get("evidence"), dict) else {}
        pointer = evidence.get("pointer") or ""
        detail = evidence.get("detail") or ""
        lines.append(f"{human}  {action:4}  {typ:16}  {weight_text} applied{cap}")
        lines.append(f"  {reason}")
        if pointer:
            extra = f" — {detail}" if detail else ""
            lines.append(f"  evidence ({evidence.get('kind')}): {pointer}{extra}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _human_ts(value: str) -> str:
    stamp = meter.parse_ts(value)
    try:
        text = stamp.strftime("%Y-%m-%d %-I:%M %p")
    except ValueError:
        text = stamp.strftime("%Y-%m-%d %I:%M %p").lstrip("0").replace(" 0", " ")
    return text


