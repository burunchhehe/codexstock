from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]
THIRD_PARTY_ROOT = REPO_ROOT / "third_party"


def third_party_path(name: str) -> Path:
    return THIRD_PARTY_ROOT / name
