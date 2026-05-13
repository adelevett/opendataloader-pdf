from __future__ import annotations

import os
from pathlib import Path

DEFAULT_INVENTORY_JSON = Path(
    r"C:\Users\delevetta\PDLay\data\extended_validation\chapter_paths_inventory\chapter_inventory.json"
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def calibre_work_dir() -> Path:
    return repo_root() / ".calibre-work"


def calibre_artifacts_dir() -> Path:
    return repo_root() / ".calibre-artifacts"


def default_inventory_path() -> Path:
    env = os.environ.get("CALIBRE_INVENTORY_JSON")
    if env:
        return Path(env)
    return DEFAULT_INVENTORY_JSON


def ensure_calibre_dirs(work_dir: Path | None = None, artifact_dir: Path | None = None) -> tuple[Path, Path]:
    work = work_dir or calibre_work_dir()
    art = artifact_dir or calibre_artifacts_dir()
    work.mkdir(parents=True, exist_ok=True)
    art.mkdir(parents=True, exist_ok=True)
    (work / "metadata_cache").mkdir(parents=True, exist_ok=True)
    return work, art

