#!/usr/bin/env python3
from __future__ import annotations

import unittest
from datetime import timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import journal
import meter
import paths
from tests.helpers import Isolate, evidence


class TestCap(unittest.TestCase):
    def setUp(self) -> None:
        self.now = paths.now().replace(microsecond=0)

    def _earn(self, weight: float, ident: str, when=None) -> dict:
        stamp = when or self.now
        return {
            "id": ident,
            "ts": stamp.isoformat(timespec="seconds"),
            "action": "earn",
            "type": "finished_build",
            "requested_weight": weight,
            "applied_weight": weight,
            "capped": False,
            "reason": "cap fixture earn",
            "evidence": evidence(),
        }

    def test_three_earns_are_clipped_to_the_daily_cap(self):
        first = self._earn(0.6, "a")
        second = self._earn(0.6, "b")
        applied, capped, remaining = meter.apply_daily_cap(
            [first, second], 0.6, self.now
        )
        self.assertTrue(capped)
        self.assertAlmostEqual(applied, 0.3, places=4)
        self.assertAlmostEqual(remaining, 0.3, places=4)
        third = dict(self._earn(0.6, "c"))
        third["applied_weight"] = applied
        third["capped"] = True
        third["requested_weight"] = 0.6
        snapshot = meter.compute([first, second, third], now=self.now)
        self.assertAlmostEqual(snapshot.rise_used_today, meter.DAILY_RISE_CAP, places=4)
        self.assertAlmostEqual(snapshot.level, 5.0 + meter.DAILY_RISE_CAP, places=4)

    def test_further_earns_apply_zero_once_the_cap_is_full(self):
        used = [
            self._earn(0.8, "a"),
            self._earn(0.7, "b"),
        ]
        used[1]["applied_weight"] = 0.7
        # 0.8 + 0.7 = 1.5, cap is full.
        applied, capped, remaining = meter.apply_daily_cap(used, 0.4, self.now)
        self.assertTrue(capped)
        self.assertEqual(applied, 0.0)
        self.assertEqual(remaining, 0.0)

    def test_dings_do_not_consume_the_rise_cap(self):
        earn = self._earn(0.8, "earn")
        ding = {
            "id": "ding",
            "ts": self.now.isoformat(timespec="seconds"),
            "action": "ding",
            "type": "miss",
            "requested_weight": -0.5,
            "applied_weight": -0.5,
            "capped": False,
            "reason": "cap fixture ding",
            "evidence": evidence("miss", "/tmp/fixture/miss-log"),
        }
        used = meter.rise_used_on_day([earn, ding], paths.today_key(self.now))
        self.assertAlmostEqual(used, 0.8, places=4)
        applied, capped, remaining = meter.apply_daily_cap([earn, ding], 0.7, self.now)
        self.assertFalse(capped)
        self.assertAlmostEqual(applied, 0.7, places=4)
        self.assertAlmostEqual(remaining, 0.7, places=4)

    def test_cap_resets_the_next_calendar_day(self):
        today = self._earn(0.8, "today")
        tomorrow = self.now + timedelta(days=1)
        applied, capped, remaining = meter.apply_daily_cap([today], 0.8, tomorrow)
        self.assertFalse(capped)
        self.assertAlmostEqual(applied, 0.8, places=4)
        self.assertAlmostEqual(remaining, meter.DAILY_RISE_CAP, places=4)

    def test_one_day_cannot_farm_into_careful_mode(self):
        events = []
        for i in range(6):
            applied, capped, _ = meter.apply_daily_cap(events, 0.8, self.now)
            record = self._earn(0.8, f"farm-{i}")
            record["requested_weight"] = 0.8
            record["applied_weight"] = applied
            record["capped"] = capped
            events.append(record)
        snapshot = meter.compute(events, now=self.now)
        self.assertAlmostEqual(snapshot.level, 5.0 + meter.DAILY_RISE_CAP, places=4)
        self.assertLessEqual(snapshot.level, meter.CAREFUL_ABOVE)
        self.assertFalse(snapshot.careful)
        self.assertTrue(any(e["capped"] for e in events))


class TestCapThroughJournal(unittest.TestCase):
    def test_seed_weights_fit_or_clip_honestly(self, tmp=None):
        # Exercised more fully in test_cli; here just the math for today's seeds.
        total = sum(
            item["requested_weight"]
            for item in __import__("seed").SEED_EVENTS
            if item["requested_weight"] > 0
        )
        self.assertLessEqual(total, meter.DAILY_RISE_CAP + 1e-9)


if __name__ == "__main__":
    unittest.main()
