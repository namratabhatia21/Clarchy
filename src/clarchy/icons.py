"""Finds official provider icons in a locally downloaded asset package.

Clarchy does not ship provider icons. Each provider publishes its own icon set under
its own terms, so users download it themselves and point Clarchy at the folder:

    export CLARCHY_ICONS_AWS=~/Downloads/Asset-Package
    clarchy render serverless-web-app --provider aws -o out.svg

Without icons the renderer draws neutral lettered badges instead.
"""

from __future__ import annotations

import base64
import os
import re
from pathlib import Path

_MIME = {".svg": "image/svg+xml", ".png": "image/png"}
# Prefer vector files, and 48/64 px variants over tiny or huge ones.
_SIZE_PREFERENCE = {"48": 0, "64": 1, "32": 2, "16": 3}


def icon_dir_from_env(provider: str) -> Path | None:
    value = os.environ.get(f"CLARCHY_ICONS_{provider.upper()}")
    return Path(value).expanduser() if value else None


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
