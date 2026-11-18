#!/usr/bin/env python3
from __future__ import annotations

import unittest
from datetime import timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import meter
import paths


class TestCareful(unittest.TestCase):
    def setUp(self) -> None:
        self.now = paths.now().replace(microsecond=0)

    def _event(self, weight: float, ident: str, hours_ago: float = 0) -> dict:
        ts = (self.now - timedelta(hours=hours_ago)).isoformat(timespec="seconds")
        return {
            "id": ident,
            "ts": ts,
            "action": "earn" if weight > 0 else "ding",
            "type": "finished_build" if weight > 0 else "miss",
            "requested_weight": weight,
            "applied_weight": weight,
            "capped": False,
            "reason": "careful fixture",
            "evidence": {
                "kind": "finished_build" if weight > 0 else "miss",
                "pointer": "/tmp/fixture/careful",
            },
        }

    def test_exactly_eight_is_not_careful(self):
        # 5 + 0.8 + 0.8 + 0.8 + 0.6 = 8.0 exactly, if all are fresh.
        weights = [0.8, 0.8, 0.8, 0.6]
        events = [self._event(w, f"e{i}") for i, w in enumerate(weights)]
        # Pin timestamps to now so decay is 1.0.
        for event in events:
            event["ts"] = self.now.isoformat(timespec="seconds")
        snapshot = meter.compute(events, now=self.now)
        self.assertAlmostEqual(snapshot.level, 8.0, places=6)
        self.assertFalse(snapshot.careful)
        text = meter.format_status(snapshot)
        self.assertIn("Careful: no", text)
        self.assertNotIn(meter.CAREFUL_TEXT, text)

    def test_above_eight_sets_the_flag(self):
        events = [self._event(0.8, f"e{i}") for i in range(4)]
        # 5 + 3.2 = 8.2
        for event in events:
            event["ts"] = self.now.isoformat(timespec="seconds")
        snapshot = meter.compute(events, now=self.now)
        self.assertGreater(snapshot.level, 8.0)
        self.assertTrue(snapshot.careful)
        status = meter.format_status(snapshot)
        explain = meter.format_explain(snapshot)
        self.assertIn("Careful: YES", status)
        self.assertIn(meter.CAREFUL_TEXT, status)
        self.assertIn(meter.CAREFUL_TEXT, explain)
        self.assertIn("humility mode", status.lower())
        self.assertIn("god complex", status.lower())

    def test_dropping_back_through_eight_clears_the_flag(self):
        events = [self._event(0.8, f"e{i}") for i in range(4)]
        for event in events:
            event["ts"] = self.now.isoformat(timespec="seconds")
        now_later = self.now + timedelta(days=3)
        snapshot = meter.compute(events, now=now_later)
        # 5 + 3.2 * 0.5 = 6.6
        self.assertAlmostEqual(snapshot.level, 6.6, places=6)
        self.assertFalse(snapshot.careful)


if __name__ == "__main__":
    unittest.main()
