#!/usr/bin/env python3
"""Idempotent seed of example pride events (replace with your own).

Safe to re-run: each event has a stable id, and a second pass writes nothing.
Chat-event minutes that were not recorded are marked as approximate and
placed earlier the same day than the afternoon builds.
"""

from __future__ import annotations

from typing import Any

import journal
import meter

# Example events only. They are made up to show the format; replace them with
# your own real, evidenced events (each with a pointer your human can check).
SEED_EVENTS: list[dict[str, Any]] = [
    {
        "id": "example-2026-01-05-name-blank",
        "ts": "2026-01-05T13:00:00-06:00",
        "action": "ding",
        "type": "mistake_caught",
        "requested_weight": -0.35,
        "reason": "Example: blanked on a name the owner had already shared.",
        "evidence": {
            "kind": "owner_caught",
            "pointer": "chat, 2026-01-05 (example)",
            "detail": "Led to a check-memory-first rule (example).",
        },
    },
    {
        "id": "example-2026-01-05-rule-compliment",
        "ts": "2026-01-05T13:30:00-06:00",
        "action": "earn",
        "type": "owner_compliment",
        "requested_weight": 0.35,
        "reason": "Example: the owner signed off on the new check-memory rule.",
        "evidence": {
            "kind": "owner_compliment",
            "pointer": "chat, 2026-01-05 (example): \"good job\"",
            "detail": "About the rule that followed the miss (example).",
        },
    },
    {
        "id": "example-2026-01-05-range-qual",
        "ts": "2026-01-05T15:00:00-06:00",
        "action": "earn",
        "type": "range_qual",
        "requested_weight": 0.40,
        "reason": "Example: passed a practice qualification on a test range.",
        "evidence": {
            "kind": "range_qual",
            "pointer": "your-range/SCOREBOARD.md (example)",
            "detail": "Example score line.",
        },
    },
    {
        "id": "example-2026-01-05-patch",
        "ts": "2026-01-05T15:10:00-06:00",
        "action": "earn",
        "type": "finished_build",
        "requested_weight": 0.35,
        "reason": "Example: a defensive patch landed with tests green.",
        "evidence": {
            "kind": "tests_passing",
            "pointer": "tests/ (example)",
            "detail": "python3 -m unittest discover -s tests reported OK (example).",
        },
    },
    {
        "id": "example-2026-01-05-tool-live",
        "ts": "2026-01-05T15:40:00-06:00",
        "action": "earn",
        "type": "finished_build",
        "requested_weight": 0.35,
        "reason": "Example: a new helper tool went live, its tests green.",
        "evidence": {
            "kind": "tests_passing",
            "pointer": "helper/tests/ (example)",
            "detail": "All helper tests OK (example).",
        },
    },
]


def existing_ids(events: list[dict[str, Any]] | None = None) -> set[str]:
    records = events if events is not None else journal.read_events()
    return {str(event.get("id") or "") for event in records if event.get("id")}


def seed_today(log_file=None) -> int:
    """Append any missing seed events. Returns how many were written."""
    journal.verify_chain(log_file)
    events = journal.read_events(log_file)
    have = existing_ids(events)
    added = 0
    working = list(events)
    for item in SEED_EVENTS:
        if item["id"] in have:
            continue
        cleaned = meter.validate_event(
            action=item["action"],
            event_type=item["type"],
            weight=item["requested_weight"],
            reason=item["reason"],
            evidence=item["evidence"],
        )
        when = meter.parse_ts(item["ts"])
        applied, capped, _remaining = meter.apply_daily_cap(
            working, cleaned["requested_weight"], when
        )
        record = {
            "id": item["id"],
            "ts": item["ts"],
            "action": cleaned["action"],
            "type": cleaned["type"],
            "requested_weight": cleaned["requested_weight"],
            "applied_weight": applied,
            "capped": capped,
            "reason": cleaned["reason"],
            "evidence": cleaned["evidence"],
            "actor": "seed.py",
        }
        written = journal.append(record, log_file=log_file)
        working.append(written)
        have.add(item["id"])
        added += 1
    if log_file is None:
        snapshot = meter.compute(journal.read_events())
        journal.snapshot_state(snapshot)
    return added


def main() -> int:
    added = seed_today()
    print(f"Seeded {added} event(s)." if added else "Seed already on the book.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
