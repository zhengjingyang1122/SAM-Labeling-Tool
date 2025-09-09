# modules/photo.py
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, QTimer
from PySide6.QtMultimedia import QImageCapture

from utils.utils import build_burst_path, build_snapshot_path, ensure_dir


class PhotoCapture(QObject):
    def __init__(self, image_capture: QImageCapture, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._cap = image_capture

    def _ready(self) -> bool:
        try:
            return self._cap.isReadyForCapture()
        except Exception:
            return True

    def capture_single(self, save_dir: Path, on_saved: Optional[Callable[[Path], None]] = None):
        path = build_snapshot_path(save_dir)
        self._capture_with_retry(path, on_saved=on_saved)

    def capture_burst_one(
        self,
        save_dir: Path,
        series_id: str,
        index: int,
        on_saved: Optional[Callable[[Path], None]] = None,
    ):
        path = build_burst_path(save_dir, series_id, index)
        self._capture_with_retry(path, on_saved=on_saved)

    def _capture_with_retry(
        self, path: Path, on_saved: Optional[Callable[[Path], None]] = None, retry_ms: int = 50
    ):
        if self._ready():
            self._cap.captureToFile(str(path))
            if on_saved:
                on_saved(path)
        else:
            QTimer.singleShot(retry_ms, lambda: self._capture_with_retry(path, on_saved, retry_ms))
