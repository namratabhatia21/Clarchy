"""Print the notes for one version from CHANGELOG.md, for the GitHub release.

    python scripts/release_notes.py 0.1.0 > notes.md

The section is everything under "## [0.1.0]" up to the next "## [" heading. A version with
no section is an error, so a release can't go out without its notes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def notes(version: str, text: str) -> str:
    match = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.M | re.S)
    if not match or not match.group(1).strip():
        raise SystemExit(f"CHANGELOG.md has no notes for {version}")
    return match.group(1).strip() + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/release_notes.py <version>")
    sys.stdout.write(notes(sys.argv[1].removeprefix("v"), CHANGELOG.read_text("utf-8")))
