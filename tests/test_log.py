#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import journal
import meter
from tests.helpers import Isolate, evidence


class TestLogAppendOnly(unittest.TestCase):
    def _record(self, ident: str, reason: str = "log fixture") -> dict:
        return {
            "id": ident,
            "ts": "2026-11-17T16:00:00-06:00",
            "action": "earn",
            "type": "finished_build",
            "requested_weight": 0.3,
            "applied_weight": 0.3,
            "capped": False,
            "reason": reason,
            "evidence": evidence(),
            "actor": "test",
        }

    def test_append_does_not_change_prior_lines(self):
        with tempfile.TemporaryDirectory() as raw:
            with Isolate(Path(raw)) as iso:
                path = iso.data / "logs" / "pride.jsonl"
                journal.append(self._record("one", "first event"), log_file=path)
                before = path.read_bytes()
                journal.append(self._record("two", "second event"), log_file=path)
                after = path.read_bytes()
                self.assertTrue(after.startswith(before))
                self.assertGreater(len(after), len(before))
                lines = after.splitlines()
                self.assertEqual(len(lines), 2)
                self.assertEqual(json.loads(lines[0])["id"], "one")
                self.assertEqual(json.loads(lines[1])["id"], "two")

    def test_hash_chain_verifies(self):
        with tempfile.TemporaryDirectory() as raw:
            with Isolate(Path(raw)) as iso:
                path = iso.data / "logs" / "pride.jsonl"
                journal.append(self._record("one"), log_file=path)
                journal.append(self._record("two"), log_file=path)
                journal.verify_chain(path)
                events = journal.read_events(path)
                self.assertEqual(events[0]["prev_hash"], journal.GENESIS_HASH)
                self.assertEqual(events[0]["seq"], 1)
                self.assertEqual(events[1]["seq"], 2)
                first_line = path.read_text(encoding="utf-8").splitlines()[0]
                self.assertEqual(events[1]["prev_hash"], journal.line_hash(first_line))

    def test_tampered_line_breaks_the_chain(self):
        with tempfile.TemporaryDirectory() as raw:
            with Isolate(Path(raw)) as iso:
                path = iso.data / "logs" / "pride.jsonl"
                journal.append(self._record("one"), log_file=path)
                journal.append(self._record("two"), log_file=path)
                lines = path.read_text(encoding="utf-8").splitlines()
                first = json.loads(lines[0])
                first["applied_weight"] = 0.8
                # A mid-file rewrite, which this module has no API for.
                path.write_text(
                    json.dumps(first, separators=(",", ":"), sort_keys=True)
                    + "\n"
                    + lines[1]
                    + "\n",
                    encoding="utf-8",
                )
                with self.assertRaises(journal.LogTampered):
                    journal.verify_chain(path)

    def test_no_rewrite_or_delete_api(self):
        forbidden = {
            "rewrite",
            "overwrite",
            "delete_record",
            "truncate",
            "edit",
            "replace_log",
            "remove_event",
            "rewrite_log",
        }
        names = {name for name in dir(journal) if not name.startswith("_")}
        self.assertTrue(forbidden.isdisjoint(names))
        # append opens in 'a' mode — confirmed by the prefix test above.
        self.assertTrue(callable(journal.append))
        self.assertTrue(callable(journal.read_events))

    def test_readable_log_view(self):
        with tempfile.TemporaryDirectory() as raw:
            with Isolate(Path(raw)) as iso:
                path = iso.data / "logs" / "pride.jsonl"
                journal.append(
                    self._record("one", "Homoglyph patch landed, tests green."),
                    log_file=path,
                )
                text = journal.format_log(journal.read_events(path))
                self.assertIn("Append-only", text)
                self.assertIn("EARN", text)
                self.assertIn("Homoglyph patch landed, tests green.", text)
                self.assertIn("/tmp/pride-test/artifact.py", text)
                self.assertIn("+0.30 applied", text)

    def test_append_after_tamper_refuses_to_write(self):
        with tempfile.TemporaryDirectory() as raw:
            with Isolate(Path(raw)) as iso:
                path = iso.data / "logs" / "pride.jsonl"
                journal.append(self._record("one"), log_file=path)
                # Corrupt the only line.
                path.write_text('{"id":"one","prev_hash":"nope","seq":1}\n', encoding="utf-8")
                before = path.read_bytes()
                with self.assertRaises(journal.LogTampered):
                    journal.append(self._record("two"), log_file=path)
                self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
