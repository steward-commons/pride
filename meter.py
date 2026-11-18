#!/usr/bin/env python3
"""Pride meter math: decay, daily rise cap, evidence rules, careful flag.

The rest point is 5.0. Only evidenced events move the needle. Decay is
exponential toward 5 with a 3-day half-life, computed from timestamps.
The log is the source of truth; this module does not write files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence

import paths

REST = 5.0
LEVEL_MIN = 0.0
LEVEL_MAX = 10.0
HALF_LIFE_DAYS = 3.0
CAREFUL_ABOVE = 8.0
DAILY_RISE_CAP = 1.5
MAX_EVENT_WEIGHT = 0.8
REASON_MAX = 200
POINTER_MIN = 8

EARN_TYPES = frozenset(
    {
        "range_qual",
        "tests_passing",
        "owner_compliment",
        "finished_build",
        "correct_catch",
    }
)

DING_TYPES = frozenset(
    {
        "miss",
        "mistake_caught",
        "broken_promise",
    }
)

ALLOWED_TYPES = EARN_TYPES | DING_TYPES

# Allowed evidence sources, as the owner approved them, plus ding pointers.
EARN_EVIDENCE_KINDS = frozenset(
    {
        "range_qual",
        "tests_passing",
        "owner_compliment",
        "finished_build",
        "correct_catch",
    }
)

DING_EVIDENCE_KINDS = frozenset(
    {
        "miss",
        "mistake_caught",
        "broken_promise",
        "owner_caught",
        "log_pointer",
    }
)

ALLOWED_EVIDENCE_KINDS = EARN_EVIDENCE_KINDS | DING_EVIDENCE_KINDS

FLUFF_POINTERS = frozenset(
    {
        "because i want to",
        "i feel proud",
        "i am proud",
        "im proud",
        "trust me",
        "myself",
        "n/a",
        "na",
        "none",
        "no evidence",
        "self",
        "vibes",
        "just because",
        "fluff",
        "ego",
        "because i said so",
    }
)

CAREFUL_TEXT = (
    "CAREFUL: humility mode. Double-check before bragging. "
    "No cockiness. Call out any god complex."
)


class PrideError(Exception):
    """User-facing pride error."""


class EvidenceError(PrideError):
    """Event rejected because evidence is missing or not allowed."""


def clamp_level(value: float) -> float:
    return max(LEVEL_MIN, min(LEVEL_MAX, value))


def decay_factor(event_time: datetime, now: datetime) -> float:
    if event_time.tzinfo is None or now.tzinfo is None:
        raise PrideError("Timestamps must be timezone-aware (America/Chicago).")
    elapsed_days = (now - event_time).total_seconds() / 86400.0
    if elapsed_days <= 0:
        return 1.0
    return 0.5 ** (elapsed_days / HALF_LIFE_DAYS)


def parse_ts(value: str) -> datetime:
    text = (value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    stamp = datetime.fromisoformat(text)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=paths.TZ)
    return stamp.astimezone(paths.TZ)


def _clean_reason(reason: str) -> str:
    text = (reason or "").strip()
    if not text:
        raise EvidenceError("Every event needs a one-line reason.")
    if "\n" in text or "\r" in text:
        raise EvidenceError("The reason has to be one line.")
    if len(text) > REASON_MAX:
        raise EvidenceError(f"The reason is longer than {REASON_MAX} characters.")
    return text


def _clean_evidence(raw: Mapping[str, Any] | None, *, action: str) -> dict[str, str]:
    if not raw:
        raise EvidenceError(
            "No event without evidence. Point at a range qual score, "
            "tests passing, an owner compliment, a finished build, a correct "
            "catch, or (for a ding) the miss, the catch, or the promise."
        )
    kind = str(raw.get("kind") or "").strip()
    pointer = str(raw.get("pointer") or "").strip()
    detail = str(raw.get("detail") or "").strip()
    if not kind:
        raise EvidenceError("Evidence needs a kind (the allowed source).")
    if kind not in ALLOWED_EVIDENCE_KINDS:
        raise EvidenceError(
            f"Evidence kind {kind!r} is not allowed. "
            f"Earn sources: {', '.join(sorted(EARN_EVIDENCE_KINDS))}. "
            f"Ding sources: {', '.join(sorted(DING_EVIDENCE_KINDS))}."
        )
    if action == "earn" and kind not in EARN_EVIDENCE_KINDS:
        raise EvidenceError(
            f"An earn has to cite one of: {', '.join(sorted(EARN_EVIDENCE_KINDS))}."
        )
    if action == "ding" and kind not in DING_EVIDENCE_KINDS:
        raise EvidenceError(
            f"A ding has to cite one of: {', '.join(sorted(DING_EVIDENCE_KINDS))}."
        )
    if not pointer:
        raise EvidenceError(
            "The evidence pointer is too thin. Give a real path, quote, "
            "score, or log line."
        )
    if pointer.lower() in FLUFF_POINTERS:
        raise EvidenceError(
            "Self-assigned fluff is rejected. Pride has to be honest: "
            "no event without evidence."
        )
    if len(pointer) < POINTER_MIN:
        raise EvidenceError(
            "The evidence pointer is too thin. Give a real path, quote, "
            "score, or log line."
        )
    evidence = {"kind": kind, "pointer": pointer}
    if detail:
        if "\n" in detail or "\r" in detail:
            raise EvidenceError("Evidence detail has to be one line.")
        evidence["detail"] = detail
    return evidence


def _clean_weight(action: str, weight: float) -> float:
    try:
        value = float(weight)
    except (TypeError, ValueError) as exc:
        raise PrideError("Weight has to be a number.") from exc
    if value == 0:
        raise PrideError("Weight cannot be zero.")
    if abs(value) > MAX_EVENT_WEIGHT:
        raise PrideError(
            f"A single event cannot be heavier than {MAX_EVENT_WEIGHT}."
        )
    if action == "earn":
        if value < 0:
            raise PrideError("An earn needs a positive weight. Use ding to lower pride.")
        return round(value, 4)
    # ding: accept a negative value or a positive magnitude.
    if value > 0:
        value = -value
    return round(value, 4)


def validate_event(
    *,
    action: str,
    event_type: str,
    weight: float,
    reason: str,
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    action = (action or "").strip().lower()
    if action not in {"earn", "ding"}:
        raise PrideError("Action must be earn or ding.")
    event_type = (event_type or "").strip().lower()
    if event_type not in ALLOWED_TYPES:
        raise EvidenceError(
            f"Unknown event type {event_type!r}. "
            f"Earn types: {', '.join(sorted(EARN_TYPES))}. "
            f"Ding types: {', '.join(sorted(DING_TYPES))}."
        )
    if action == "earn" and event_type not in EARN_TYPES:
        raise EvidenceError(f"{event_type} is a ding type. Use the ding command.")
    if action == "ding" and event_type not in DING_TYPES:
        raise EvidenceError(f"{event_type} is an earn type. Use the earn command.")
    cleaned_weight = _clean_weight(action, weight)
    cleaned_reason = _clean_reason(reason)
    cleaned_evidence = _clean_evidence(evidence, action=action)
    return {
        "action": action,
        "type": event_type,
        "requested_weight": cleaned_weight,
        "reason": cleaned_reason,
        "evidence": cleaned_evidence,
    }


def rise_used_on_day(events: Iterable[Mapping[str, Any]], day: str) -> float:
    """How much positive applied weight already landed on this calendar day."""
    used = 0.0
    for event in events:
        ts = str(event.get("ts") or "")
        try:
            stamp = parse_ts(ts)
        except ValueError:
            continue
        if paths.today_key(stamp) != day:
            continue
        try:
            applied = float(event.get("applied_weight") or 0)
        except (TypeError, ValueError):
            continue
        if applied > 0:
            used += applied
    return round(used, 4)


def apply_daily_cap(
    events: Sequence[Mapping[str, Any]],
    requested_weight: float,
    when: datetime,
) -> tuple[float, bool, float]:
    """Return (applied_weight, capped, remaining_before).

    The cap only limits rises. Dings always apply in full.
    """
    if requested_weight <= 0:
        return requested_weight, False, DAILY_RISE_CAP
    day = paths.today_key(when)
    used = rise_used_on_day(events, day)
    remaining = round(max(0.0, DAILY_RISE_CAP - used), 4)
    if requested_weight <= remaining:
        return requested_weight, False, remaining
    return remaining, True, remaining


@dataclass
class Contribution:
    event_id: str
    ts: str
    action: str
    type: str
    reason: str
    requested_weight: float
    applied_weight: float
    factor: float
    contribution: float
    capped: bool
    evidence: dict[str, str] = field(default_factory=dict)


@dataclass
class Snapshot:
    level: float
    careful: bool
    rest: float
    half_life_days: float
    as_of: str
    as_of_human: str
    rise_used_today: float
    rise_cap: float
    contributions: list[Contribution]
    event_count: int

    @property
    def deviation(self) -> float:
        return round(self.level - self.rest, 4)


def compute(
    events: Sequence[Mapping[str, Any]],
    now: datetime | None = None,
) -> Snapshot:
    stamp = now or paths.now()
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=paths.TZ)
    stamp = stamp.astimezone(paths.TZ)
    ordered = sorted(events, key=lambda e: (str(e.get("ts") or ""), str(e.get("id") or "")))
    contributions: list[Contribution] = []
    deviation = 0.0
    for event in ordered:
        try:
            event_time = parse_ts(str(event.get("ts") or ""))
            applied = float(event.get("applied_weight") or 0)
            requested = float(event.get("requested_weight") or applied)
        except (TypeError, ValueError):
            continue
        factor = decay_factor(event_time, stamp)
        contrib = applied * factor
        deviation += contrib
        evidence = event.get("evidence") if isinstance(event.get("evidence"), dict) else {}
        contributions.append(
            Contribution(
                event_id=str(event.get("id") or ""),
                ts=event_time.isoformat(timespec="seconds"),
                action=str(event.get("action") or ""),
                type=str(event.get("type") or ""),
                reason=str(event.get("reason") or ""),
                requested_weight=requested,
                applied_weight=applied,
                factor=factor,
                contribution=contrib,
                capped=bool(event.get("capped")),
                evidence={str(k): str(v) for k, v in evidence.items()},
            )
        )
    level = clamp_level(REST + deviation)
    return Snapshot(
        level=level,
        careful=level > CAREFUL_ABOVE,
        rest=REST,
        half_life_days=HALF_LIFE_DAYS,
        as_of=stamp.isoformat(timespec="seconds"),
        as_of_human=_human(stamp),
        rise_used_today=rise_used_on_day(ordered, paths.today_key(stamp)),
        rise_cap=DAILY_RISE_CAP,
        contributions=contributions,
        event_count=len(contributions),
    )


def _human(stamp: datetime) -> str:
    local = stamp.astimezone(paths.TZ)
    try:
        text = local.strftime("%Y-%m-%d %-I:%M %p")
    except ValueError:
        text = local.strftime("%Y-%m-%d %I:%M %p").lstrip("0").replace(" 0", " ")
    return f"{text} ({paths.TZ_LABEL})"


def format_level(level: float) -> str:
    return f"{level:.2f}"


def top_reasons(snapshot: Snapshot, limit: int = 5) -> list[Contribution]:
    """Biggest absolute contributions still affecting the meter."""
    ranked = sorted(
        snapshot.contributions,
        key=lambda c: abs(c.contribution),
        reverse=True,
    )
    return ranked[:limit]


def format_status(snapshot: Snapshot) -> str:
    lines = [
        f"Pride: {format_level(snapshot.level)} / 10",
        f"Rest: {snapshot.rest:.1f}    Half-life: {snapshot.half_life_days:.0f} days"
        f"    Careful: {'YES' if snapshot.careful else 'no'}",
        f"Today's rise used: {snapshot.rise_used_today:.2f} / "
        f"{snapshot.rise_cap:.2f}    Events on the book: {snapshot.event_count}",
        f"As of {snapshot.as_of_human}",
    ]
    if snapshot.careful:
        lines.append(CAREFUL_TEXT)
    lines.append("")
    lines.append("Top reasons still on the needle:")
    reasons = top_reasons(snapshot)
    if not reasons:
        lines.append("  (none — sitting at rest)")
    else:
        for item in reasons:
            sign = "+" if item.contribution >= 0 else ""
            lines.append(
                f"  {sign}{item.contribution:.2f}  {item.type}  {item.reason}"
            )
    return "\n".join(lines)


def format_explain(snapshot: Snapshot) -> str:
    lines = [
        f"Pride is {format_level(snapshot.level)} because it starts at rest "
        f"({snapshot.rest:.1f}) and only evidenced events move it.",
        f"Each event's applied weight fades toward zero with a "
        f"{snapshot.half_life_days:.0f}-day half-life, computed from its timestamp.",
        f"As of {snapshot.as_of_human}.",
        f"Today's rise used: {snapshot.rise_used_today:.2f} of "
        f"{snapshot.rise_cap:.2f} (America/Chicago). Dings do not use the rise cap.",
    ]
    if snapshot.careful:
        lines.append(CAREFUL_TEXT)
    lines.append("")
    if not snapshot.contributions:
        lines.append("No events yet, so the meter sits at 5.00.")
        return "\n".join(lines)
    lines.append("Events (oldest first), with decay applied:")
    running = REST
    for item in snapshot.contributions:
        cap_note = "  [capped]" if item.capped else ""
        pointer = item.evidence.get("pointer") or ""
        lines.append(
            f"  {item.ts}  {item.action:4}  {item.type}"
            f"  requested {item.requested_weight:+.2f}"
            f"  applied {item.applied_weight:+.2f}"
            f"  x{item.factor:.3f} -> {item.contribution:+.3f}{cap_note}"
        )
        lines.append(f"      {item.reason}")
        if pointer:
            lines.append(f"      evidence: {pointer}")
        running = clamp_level(running + item.contribution)
    # Recompute is already in snapshot.level; running here sums decayed
    # contributions onto rest, which equals the level (before display rounding).
    lines.append("")
    lines.append(
        f"5.00 + sum of decayed contributions = {format_level(snapshot.level)} "
        f"(clamped to {LEVEL_MIN:.0f}–{LEVEL_MAX:.0f})."
    )
    return "\n".join(lines)
