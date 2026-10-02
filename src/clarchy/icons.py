"""Finds official provider icons for diagrams.

The AWS and Azure architecture icons for the services Clarchy draws ship in
data/icons/aws/ and data/icons/azure/ and are used, unchanged, in those providers'
diagrams (ADR 0012). Google Cloud icons are not bundled: users download a provider's
package themselves and point Clarchy at the folder, which also works for a newer AWS or
Azure release:

    export CLARCHY_ICONS_GCP=~/Downloads/gcp-icons
    clarchy render serverless-web-app --provider gcp -o out.svg

Without icons the renderer draws neutral lettered badges instead.
"""

from __future__ import annotations

import base64
import os
import re
from functools import cache
from importlib import resources
from pathlib import Path

_MIME = {".svg": "image/svg+xml", ".png": "image/png"}
# Prefer vector files, and 48/64 px variants over tiny or huge ones.
_SIZE_PREFERENCE = {"48": 0, "64": 1, "32": 2, "16": 3}


def icon_dir_from_env(provider: str) -> Path | None:
    value = os.environ.get(f"CLARCHY_ICONS_{provider.upper()}")
    return Path(value).expanduser() if value else None


def bundled_icon_dir(provider: str) -> Path | None:
    """The icons that ship with Clarchy for this provider (AWS and Azure)."""
    path = Path(str(resources.files("clarchy").joinpath("data", "icons", provider)))
    return path if path.is_dir() else None


@cache
def bundled_library(provider: str) -> IconLibrary:
    return IconLibrary(bundled_icon_dir(provider))


def icon_library(provider: str, explicit: Path | None = None) -> IconLibrary:
    """The icons for one provider: an explicit folder, else CLARCHY_ICONS_<PROVIDER>, else
    the icons bundled with Clarchy, else none (lettered badges)."""
    root = explicit or icon_dir_from_env(provider)
    return IconLibrary(root) if root else bundled_library(provider)


class IconLibrary:
    def __init__(self, root: Path | None):
        self.root = root
        self._files: list[Path] = []
        if root is not None:
            if not root.is_dir():
                raise FileNotFoundError(f"icon directory not found: {root}")
            self._files = sorted(
                p for p in root.rglob("*") if p.suffix.lower() in _MIME and p.is_file()
            )

    def find(self, stem: str | None) -> Path | None:
        if not stem or not self._files:
            return None
        pattern = re.compile(rf"(^|_){re.escape(stem)}(_|\.)", re.IGNORECASE)
        matches = [p for p in self._files if pattern.search(p.name)]
        if not matches:
            return None

        def rank(path: Path) -> tuple[int, int, str]:
            size = re.search(r"_(\d+)(?:@\dx)?\.\w+$", path.name)
            size_rank = _SIZE_PREFERENCE.get(size.group(1), 9) if size else 5
            return (0 if path.suffix.lower() == ".svg" else 1, size_rank, path.as_posix())

        return min(matches, key=rank)

    def data_uri(self, stem: str | None) -> str | None:
        path = self.find(stem)
        if path is None:
            return None
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{_MIME[path.suffix.lower()]};base64,{encoded}"
