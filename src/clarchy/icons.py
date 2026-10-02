"""Finds official provider icons for diagrams.

Icons ship for every provider (ADR 0012): the AWS, Azure and Google Cloud architecture
icons for the services Clarchy draws, in data/icons/<provider>/, used unchanged in that
provider's diagrams; and open-source projects' own logos in data/icons/oss/. A mapping's
`icon:` names a file stem; `oss:<stem>` borrows a project logo for a cloud diagram (LiteLLM
on Cloud Run). A user can point Clarchy at a provider's newer package instead:

    export CLARCHY_ICONS_AWS=~/Downloads/Asset-Package
    clarchy render serverless-web-app --provider aws -o out.svg

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
    """The icons that ship with Clarchy for this provider."""
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
        if not stem or self.root is None:
            return None
        if stem.startswith("oss:"):  # an open-source project's logo, e.g. LiteLLM on GCP
            return bundled_library("oss").find(stem.removeprefix("oss:"))
        if not self._files:
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
