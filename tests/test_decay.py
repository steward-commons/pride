#!/usr/bin/env python3
from __future__ import annotations

import unittest
from datetime import timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import meter
import paths


class TestDecay(unittest.TestCase):
    def setUp(self) -> None:
        self.now = paths.now().replace(microsecond=0)

    def _event(self, hours_ago: float, weight: float, ident: str = "e") -> dict:
        ts = (self.now - timedelta(hours=hours_ago)).isoformat(timespec="seconds")
        return {
            "id": ident,
            "ts": ts,
            "action": "earn" if weight > 0 else "ding",
            "type": "finished_build" if weight > 0 else "miss",
            "requested_weight": weight,
            "applied_weight": weight,
            "capped": False,
            "reason": "decay fixture",
            "evidence": {"kind": "finished_build" if weight > 0 else "miss", "pointer": "/tmp/fixture/evidence"},
        }

    def test_rest_with_no_events(self):
        snapshot = meter.compute([], now=self.now)
        self.assertAlmostEqual(snapshot.level, 5.0)
        self.assertFalse(snapshot.careful)

    def test_half_life_is_three_days(self):
        weight = 0.8
        event = self._event(hours_ago=3 * 24, weight=weight, ident="half")
        snapshot = meter.compute([event], now=self.now)
        # After one half-life the contribution is half the applied weight.
        self.assertAlmostEqual(snapshot.contributions[0].factor, 0.5, places=6)
        self.assertAlmostEqual(snapshot.contributions[0].contribution, weight * 0.5, places=6)
        self.assertAlmostEqual(snapshot.level, 5.0 + weight * 0.5, places=6)

    def test_two_half_lives(self):
        weight = 0.8
        event = self._event(hours_ago=6 * 24, weight=weight, ident="quarter")
        snapshot = meter.compute([event], now=self.now)
        self.assertAlmostEqual(snapshot.contributions[0].factor, 0.25, places=6)
        self.assertAlmostEqual(snapshot.level, 5.0 + weight * 0.25, places=6)

    def test_fresh_event_does_not_decay(self):
        event = self._event(hours_ago=0, weight=0.4, ident="fresh")
        # Place it exactly at now so elapsed is 0.
        event["ts"] = self.now.isoformat(timespec="seconds")
        snapshot = meter.compute([event], now=self.now)
        self.assertAlmostEqual(snapshot.contributions[0].factor, 1.0)
        self.assertAlmostEqual(snapshot.level, 5.4, places=6)

    def test_dings_decay_toward_rest_too(self):
        event = self._event(hours_ago=3 * 24, weight=-0.6, ident="ding")
        snapshot = meter.compute([event], now=self.now)
        self.assertAlmostEqual(snapshot.level, 5.0 + (-0.6 * 0.5), places=6)

    def test_events_decay_independently_from_timestamps(self):
        fresh = self._event(hours_ago=0, weight=0.4, ident="fresh")
        fresh["ts"] = self.now.isoformat(timespec="seconds")
        old = self._event(hours_ago=3 * 24, weight=0.4, ident="old")
        snapshot = meter.compute([fresh, old], now=self.now)
        self.assertAlmostEqual(snapshot.level, 5.0 + 0.4 + 0.2, places=6)

    def test_decay_is_recomputed_not_stored(self):
        event = self._event(hours_ago=3 * 24, weight=0.8, ident="stored")
        first = meter.compute([event], now=self.now)
        later = meter.compute([event], now=self.now + timedelta(days=3))
        self.assertAlmostEqual(first.contributions[0].contribution, 0.4, places=6)
        self.assertAlmostEqual(later.contributions[0].contribution, 0.2, places=6)
        # The record itself is unchanged.
        self.assertEqual(event["applied_weight"], 0.8)


if __name__ == "__main__":
    unittest.main()
