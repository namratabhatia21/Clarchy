"""Release notes come from CHANGELOG.md, and the package version has its notes there."""

import importlib.util
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "release_notes", ROOT / "scripts" / "release_notes.py"
)
release_notes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release_notes)


def test_the_package_version_has_release_notes():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    text = release_notes.notes(version, (ROOT / "CHANGELOG.md").read_text())
    assert text.strip() and "## [" not in text, "only that version's section"


def test_notes_stop_at_the_next_version_and_refuse_a_missing_one():
    changelog = (
        "# Changelog\n\n## [1.1.0] - 2026-11-01\n\n- New\n\n## [1.0.0] - 2026-10-01\n\n- Old\n"
    )
    assert release_notes.notes("1.1.0", changelog) == "- New\n"
    assert release_notes.notes("1.0.0", changelog) == "- Old\n"
    with pytest.raises(SystemExit):
        release_notes.notes("2.0.0", changelog)
