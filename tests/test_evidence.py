#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import meter
from tests.helpers import evidence


class TestEvidenceRequired(unittest.TestCase):
    def test_missing_evidence_is_rejected(self):
        with self.assertRaises(meter.EvidenceError) as ctx:
            meter.validate_event(
                action="earn",
                event_type="finished_build",
                weight=0.3,
                reason="I did a thing",
                evidence=None,
            )
        self.assertIn("evidence", str(ctx.exception).lower())

    def test_empty_pointer_is_rejected(self):
        with self.assertRaises(meter.EvidenceError):
            meter.validate_event(
                action="earn",
                event_type="finished_build",
                weight=0.3,
                reason="I did a thing",
                evidence={"kind": "finished_build", "pointer": ""},
            )

    def test_short_pointer_is_rejected(self):
        with self.assertRaises(meter.EvidenceError) as ctx:
            meter.validate_event(
                action="earn",
                event_type="finished_build",
                weight=0.3,
                reason="I did a thing",
                evidence={"kind": "finished_build", "pointer": "short"},
            )
        self.assertIn("thin", str(ctx.exception).lower())

    def test_fluff_pointer_is_rejected(self):
        for fluff in ("trust me", "I feel proud", "myself", "n/a", "just because"):
            with self.subTest(fluff=fluff):
                with self.assertRaises(meter.EvidenceError) as ctx:
                    meter.validate_event(
                        action="earn",
                        event_type="owner_compliment",
                        weight=0.3,
                        reason="Because I want to be proud",
                        evidence={"kind": "owner_compliment", "pointer": fluff},
                    )
                self.assertIn("fluff", str(ctx.exception).lower())

    def test_unknown_type_is_rejected(self):
        with self.assertRaises(meter.EvidenceError):
            meter.validate_event(
                action="earn",
                event_type="self_praise",
                weight=0.3,
                reason="I am great",
                evidence=evidence(),
            )

    def test_earn_with_ding_type_is_rejected(self):
        with self.assertRaises(meter.EvidenceError) as ctx:
            meter.validate_event(
                action="earn",
                event_type="mistake_caught",
                weight=0.3,
                reason="Trying to raise on a ding type",
                evidence=evidence(),
            )
        self.assertIn("ding", str(ctx.exception).lower())

    def test_ding_with_earn_type_is_rejected(self):
        with self.assertRaises(meter.EvidenceError):
            meter.validate_event(
                action="ding",
                event_type="owner_compliment",
                weight=0.3,
                reason="Wrong direction",
                evidence={"kind": "owner_caught", "pointer": "The owner caught a real miss today"},
            )

    def test_earn_evidence_must_be_an_allowed_source(self):
        with self.assertRaises(meter.EvidenceError):
            meter.validate_event(
                action="earn",
                event_type="finished_build",
                weight=0.3,
                reason="Built a thing",
                evidence={"kind": "owner_caught", "pointer": "/tmp/fixture/artifact.py"},
            )

    def test_empty_reason_is_rejected(self):
        with self.assertRaises(meter.EvidenceError):
            meter.validate_event(
                action="earn",
                event_type="finished_build",
                weight=0.3,
                reason="   ",
                evidence=evidence(),
            )

    def test_multiline_reason_is_rejected(self):
        with self.assertRaises(meter.EvidenceError):
            meter.validate_event(
                action="earn",
                event_type="finished_build",
                weight=0.3,
                reason="line one\nline two",
                evidence=evidence(),
            )

    def test_zero_weight_is_rejected(self):
        with self.assertRaises(meter.PrideError):
            meter.validate_event(
                action="earn",
                event_type="finished_build",
                weight=0,
                reason="Nothing",
                evidence=evidence(),
            )

    def test_weight_over_max_is_rejected(self):
        with self.assertRaises(meter.PrideError):
            meter.validate_event(
                action="earn",
                event_type="finished_build",
                weight=1.5,
                reason="Too heavy",
                evidence=evidence(),
            )

    def test_negative_earn_weight_is_rejected(self):
        with self.assertRaises(meter.PrideError):
            meter.validate_event(
                action="earn",
                event_type="finished_build",
                weight=-0.3,
                reason="Wrong sign",
                evidence=evidence(),
            )

    def test_valid_earn_is_accepted(self):
        cleaned = meter.validate_event(
            action="earn",
            event_type="range_qual",
            weight=0.4,
            reason="Example practice qual passed.",
            evidence={
                "kind": "range_qual",
                "pointer": "range/SCOREBOARD.md",
                "detail": "Example score",
            },
        )
        self.assertEqual(cleaned["requested_weight"], 0.4)
        self.assertEqual(cleaned["evidence"]["kind"], "range_qual")

    def test_ding_accepts_positive_magnitude(self):
        cleaned = meter.validate_event(
            action="ding",
            event_type="mistake_caught",
            weight=0.35,
            reason="Blanked on a pet's name (example).",
            evidence={
                "kind": "owner_caught",
                "pointer": "The owner mentioned a pet's name and I blanked",
            },
        )
        self.assertEqual(cleaned["requested_weight"], -0.35)

    def test_ding_accepts_negative_weight(self):
        cleaned = meter.validate_event(
            action="ding",
            event_type="miss",
            weight=-0.3,
            reason="Missed a plate.",
            evidence={"kind": "miss", "pointer": "range/SCOREBOARD.md"},
        )
        self.assertEqual(cleaned["requested_weight"], -0.3)


if __name__ == "__main__":
    unittest.main()
