"""Test helpers: isolate pride data so tests never touch the live log."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PRIDE = Path(__file__).resolve().parents[1]
if str(PRIDE) not in sys.path:
    sys.path.insert(0, str(PRIDE))


class Isolate:
    """Temporarily point pride data at a temp folder."""

    def __init__(self, tmp: Path) -> None:
        self.data = tmp / "data"
        self.data.mkdir()
        (self.data / "logs").mkdir()
        self._old = os.environ.get("PRIDE_DATA")
        os.environ["PRIDE_DATA"] = str(self.data)

    def close(self) -> None:
        if self._old is None:
            os.environ.pop("PRIDE_DATA", None)
        else:
            os.environ["PRIDE_DATA"] = self._old

    def __enter__(self) -> "Isolate":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def evidence(
    kind: str = "finished_build",
    pointer: str = "/tmp/pride-test/artifact.py",
    detail: str = "unit test fixture",
) -> dict[str, str]:
    return {"kind": kind, "pointer": pointer, "detail": detail}
