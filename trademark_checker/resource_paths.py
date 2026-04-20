from __future__ import annotations

import sys
from pathlib import Path


def bundle_root() -> Path:
    root = getattr(sys, "_MEIPASS", "")
    if root:
        return Path(root)
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    root = getattr(sys, "_MEIPASS", "")
    if root:
        return Path(root) / "trademark_checker" / "data"
    return Path(__file__).resolve().parent / "data"


def docs_dir() -> Path:
    root = getattr(sys, "_MEIPASS", "")
    if root:
        return Path(root) / "docs"
    return Path(__file__).resolve().parent.parent / "docs"
