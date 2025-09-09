# utils.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Union

try:
    from PySide6.QtCore import QUrl
except Exception:
    QUrl = None  # 型別保留，避免編譯期出錯

PathLike = Union[str, Path]


def ensure_dir(p: PathLike) -> Path:
    pth = Path(p).expanduser()
    pth.mkdir(parents=True, exist_ok=True)
    return pth


def ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ts_ms() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def build_snapshot_path(save_dir: PathLike) -> Path:
    return ensure_dir(save_dir) / f"snapshot_{ts_ms()}.jpg"


def build_burst_path(save_dir: PathLike, series_id: str, index: int) -> Path:
    return ensure_dir(save_dir) / f"burst_{series_id}_{index:03d}.jpg"


def build_record_path(save_dir: PathLike) -> Path:
    return ensure_dir(save_dir) / f"record_{ts()}.mp4"


def to_qurl_or_str(path: Path) -> object:
    if QUrl is not None:
        try:
            return QUrl.fromLocalFile(str(path))
        except Exception:
            pass
    return str(path)
