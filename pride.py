#!/usr/bin/env python3
"""Pride meter front door.

Commands: status, earn, ding, log, explain, seed.

A 0-10 meter that rests at 5.0. Only evidenced, earned events move it.
It decays back toward 5 with a 3-day half-life. Above 8 is careful /
humility mode: no cockiness, and call out any god complex. State lives
in this folder. No secrets.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

import journal
import meter
import paths
import seed as seedmod



def _medical_blocked(part: str) -> str | None:
    """Return a reason if the morphine pen or a tourniquet blocks this part."""
    try:
        import importlib.util
        from pathlib import Path as _P

        # Optional hook: set PRIDE_MEDICAL_GUARD to a guard.py exposing
        # blocked(part) -> str | None (see the companion "medical" repo).
        raw = os.environ.get("PRIDE_MEDICAL_GUARD", "").strip()
        if not raw:
            return None
        guard_path = _P(raw)
        if not guard_path.is_file():
            return None
        spec = importlib.util.spec_from_file_location(
            "_steward_medical_guard", guard_path
        )
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.blocked(part)
    except Exception:
        return None

def _print(text: str) -> int:
    sys.stdout.write(text.rstrip() + "\n")
    return 0


def _fail(message: str) -> int:
    sys.stderr.write(message.rstrip() + "\n")
    return 2


def _snapshot(now=None) -> meter.Snapshot:
    journal.verify_chain()
    events = journal.read_events()
    snapshot = meter.compute(events, now=now)
    journal.snapshot_state(snapshot)
    return snapshot


def cmd_status() -> int:
    try:
        snapshot = _snapshot()
    except meter.PrideError as exc:
        return _fail(str(exc))
    return _print(meter.format_status(snapshot))


def cmd_explain() -> int:
    try:
        snapshot = _snapshot()
    except meter.PrideError as exc:
        return _fail(str(exc))
    return _print(meter.format_explain(snapshot))


def cmd_log(limit: int) -> int:
    try:
        journal.verify_chain()
        text = journal.format_log(limit=limit)
    except meter.PrideError as exc:
        return _fail(str(exc))
    return _print(text)


def cmd_event(
    *,
    action: str,
    event_type: str,
    weight: float,
    reason: str,
    evidence_kind: str,
    pointer: str,
    detail: str,
    event_id: str | None = None,
    ts: str | None = None,
) -> int:
    try:
        journal.verify_chain()
        events = journal.read_events()
        cleaned = meter.validate_event(
            action=action,
            event_type=event_type,
            weight=weight,
            reason=reason,
            evidence={
                "kind": evidence_kind,
                "pointer": pointer,
                "detail": detail,
            },
        )
        when = meter.parse_ts(ts) if ts else paths.now()
        applied, capped, remaining = meter.apply_daily_cap(
            events, cleaned["requested_weight"], when
        )
        record = {
            "id": event_id or "",
            "ts": ts or when.isoformat(timespec="seconds"),
            "action": cleaned["action"],
            "type": cleaned["type"],
            "requested_weight": cleaned["requested_weight"],
            "applied_weight": applied,
            "capped": capped,
            "reason": cleaned["reason"],
            "evidence": cleaned["evidence"],
            "actor": "pride.py",
        }
        journal.append(record)
        snapshot = _snapshot(now=paths.now())
    except meter.PrideError as exc:
        return _fail(str(exc))
    parts = [meter.format_status(snapshot)]
    if capped:
        if applied == 0:
            parts.append(
                f"\nDaily rise cap reached "
                f"({meter.DAILY_RISE_CAP:.2f}). This event was logged "
                "but did not raise the meter."
            )
        else:
            parts.append(
                f"\nDaily rise cap clipped this earn from "
                f"{cleaned['requested_weight']:+.2f} to {applied:+.2f} "
                f"({remaining:.2f} was left on the cap)."
            )
    return _print("".join(parts))


def cmd_seed() -> int:
    try:
        added = seedmod.seed_today()
        snapshot = _snapshot()
    except meter.PrideError as exc:
        return _fail(str(exc))
    if added:
        header = f"Seeded {added} event(s) from 2026-11-17.\n\n"
    else:
        header = "Seed already on the book; nothing new was written.\n\n"
    return _print(header + meter.format_status(snapshot))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pride.py",
        description=(
            "Pride meter. Rests at 5.0, moves only on evidenced events, "
            "decays toward 5 with a 3-day half-life, and goes into "
            "humility mode above 8."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show the current level, careful flag, and top reasons.")
    sub.add_parser("explain", help="Why the meter is at this level.")

    log_cmd = sub.add_parser("log", help="Readable view of the append-only pride log.")
    log_cmd.add_argument(
        "--limit",
        "-n",
        type=int,
        default=0,
        help="Show only the last N events (0 = all).",
    )

    earn = sub.add_parser("earn", help="Record an earned event that raises pride.")
    _event_args(earn, action="earn")
    ding = sub.add_parser("ding", help="Record a miss, a caught mistake, or a broken promise.")
    _event_args(ding, action="ding")

    sub.add_parser(
        "seed",
        help="Idempotent seed of the example events in seed.py. Safe to re-run.",
    )
    return parser


def _event_args(parser: argparse.ArgumentParser, *, action: str) -> None:
    parser.set_defaults(action=action)
    parser.add_argument(
        "--type",
        required=True,
        dest="event_type",
        help=(
            "Event type. Earn: range_qual, tests_passing, owner_compliment, "
            "finished_build, correct_catch. Ding: miss, mistake_caught, "
            "broken_promise."
        ),
    )
    parser.add_argument(
        "--weight",
        type=float,
        required=True,
        help=(
            "How heavy the event is, up to 0.8. For ding, a positive number "
            "is the magnitude (stored negative)."
        ),
    )
    parser.add_argument("--reason", required=True, help="One-line reason.")
    parser.add_argument(
        "--evidence-kind",
        required=True,
        help="Allowed source kind (same names as the earn types, or a ding pointer kind).",
    )
    parser.add_argument(
        "--evidence",
        required=True,
        dest="pointer",
        help="Source or evidence pointer: a path, score, quote, or log line.",
    )
    parser.add_argument(
        "--detail",
        default="",
        help="Optional one-line extra evidence (a score, quote, or test count).",
    )
    parser.add_argument(
        "--id",
        dest="event_id",
        default="",
        help="Optional stable id (used by seed so re-runs do not double-count).",
    )
    parser.add_argument(
        "--ts",
        default="",
        help="Optional timezone-aware timestamp. Default: now, America/Chicago.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "status":
        return cmd_status()
    if args.command == "explain":
        return cmd_explain()
    if args.command == "log":
        return cmd_log(args.limit)
    if args.command == "seed":
        reason = _medical_blocked("pride")
        if reason:
            return _fail(reason)
        return cmd_seed()
    if args.command in {"earn", "ding"}:
        reason = _medical_blocked("pride")
        if reason:
            return _fail(reason)
        return cmd_event(
            action=args.action,
            event_type=args.event_type,
            weight=args.weight,
            reason=args.reason,
            evidence_kind=args.evidence_kind,
            pointer=args.pointer,
            detail=args.detail,
            event_id=args.event_id or None,
            ts=args.ts or None,
        )
    return _fail(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
