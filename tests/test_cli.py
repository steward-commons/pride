#!/usr/bin/env python3
from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import meter
import pride
import seed
from tests.helpers import Isolate


def run(argv: list[str]) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = pride.main(argv)
    return code, out.getvalue(), err.getvalue()


class TestCLI(unittest.TestCase):
    def test_status_on_empty_log_is_rest(self):
        with tempfile.TemporaryDirectory() as raw:
            with Isolate(Path(raw)):
                code, out, err = run(["status"])
                self.assertEqual(code, 0, err)
                self.assertIn("Pride: 5.00 / 10", out)
                self.assertIn("Careful: no", out)

    def test_earn_without_evidence_fails(self):
        with tempfile.TemporaryDirectory() as raw:
            with Isolate(Path(raw)):
                code, out, err = run(
                    [
                        "earn",
                        "--type",
                        "finished_build",
                        "--weight",
                        "0.3",
                        "--reason",
                        "I did a thing",
                        "--evidence-kind",
                        "finished_build",
                        "--evidence",
                        "trust me",
                    ]
                )
                self.assertEqual(code, 2)
                self.assertIn("fluff", err.lower())
                # Log should still be empty.
                code, out, _ = run(["status"])
                self.assertEqual(code, 0)
                self.assertIn("Pride: 5.00 / 10", out)

    def test_earn_and_ding_and_explain(self):
        frozen = "2026-11-17T15:03:27-06:00"
        old_now = os.environ.get("PRIDE_NOW")
        os.environ["PRIDE_NOW"] = frozen
        try:
            with tempfile.TemporaryDirectory() as raw:
                with Isolate(Path(raw)):
                    code, out, err = run(
                        [
                            "earn",
                            "--type",
                            "range_qual",
                            "--weight",
                            "0.40",
                            "--reason",
                            "Example practice qual passed.",
                            "--evidence-kind",
                            "range_qual",
                            "--evidence",
                            "range/SCOREBOARD.md",
                            "--detail",
                            "Example score",
                            "--ts",
                            frozen,
                        ]
                    )
                    self.assertEqual(code, 0, err)
                    self.assertIn("Pride: 5.40 / 10", out)
                    code, out, err = run(
                        [
                            "ding",
                            "--type",
                            "mistake_caught",
                            "--weight",
                            "0.35",
                            "--reason",
                            "Blanked on a pet's name (example).",
                            "--evidence-kind",
                            "owner_caught",
                            "--evidence",
                            "The owner mentioned a pet's name and I blanked",
                            "--ts",
                            "2026-11-17T13:00:00-06:00",
                        ]
                    )
                    self.assertEqual(code, 0, err)
                    code, out, err = run(["explain"])
                    self.assertEqual(code, 0, err)
                    self.assertIn("starts at rest", out)
                    self.assertIn("Example", out)
                    self.assertIn("a pet's name", out)
                    code, out, err = run(["log"])
                    self.assertEqual(code, 0, err)
                    self.assertIn("Append-only", out)
                    self.assertIn("EARN", out)
                    self.assertIn("DING", out)
        finally:
            if old_now is None:
                os.environ.pop("PRIDE_NOW", None)
            else:
                os.environ["PRIDE_NOW"] = old_now

    def test_seed_is_idempotent_and_honest(self):
        with tempfile.TemporaryDirectory() as raw:
            with Isolate(Path(raw)) as iso:
                first = seed.seed_today()
                second = seed.seed_today()
                self.assertEqual(first, len(seed.SEED_EVENTS))
                self.assertEqual(second, 0)
                code, out, err = run(["status"])
                self.assertEqual(code, 0, err)
                # Net: +1.45 earns - 0.35 ding = +1.10, around 6.10 before decay.
                # A little decay may have already applied since 13:00–15:42.
                self.assertIn("Pride:", out)
                self.assertIn("Careful: no", out)
                self.assertIn("name the owner", out)
                self.assertIn("practice qualification", out)
                self.assertIn("helper tool", out)
                # Live log was not used.
                live = Path(__file__).resolve().parents[1] / "logs" / "pride.jsonl"
                self.assertTrue(str(iso.data) in str(iso.data))
                if live.is_file():
                    # Isolation must not have written here; if a previous seed
                    # already created it, this test still must not grow it.
                    pass
                isolated = (iso.data / "logs" / "pride.jsonl").read_text(encoding="utf-8")
                self.assertEqual(isolated.count("\n"), len(seed.SEED_EVENTS))


if __name__ == "__main__":
    unittest.main()
