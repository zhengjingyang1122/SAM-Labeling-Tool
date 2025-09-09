# modules/recorder.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject
from PySide6.QtMultimedia import QMediaRecorder

from utils.utils import build_record_path, ensure_dir, to_qurl_or_str


class VideoRecorder(QObject):
    def __init__(self, recorder: QMediaRecorder, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._rec = recorder
        self._has_location = False

    def start_or_resume(self, save_dir: Path):
        ensure_dir(save_dir)
        # 若未設定過輸出路徑，配置新檔案
        state = None
        try:
            state = self._rec.recorderState()
        except Exception:
            try:
                state = self._rec.state()
            except Exception:
                pass

        if (
            state not in (QMediaRecorder.RecordingState, QMediaRecorder.PausedState)
            or not self._has_location
        ):
            out_path = build_record_path(save_dir)
            self._rec.setOutputLocation(to_qurl_or_str(out_path))  # QUrl 或 str
            self._has_location = True

        self._rec.record()

    def pause(self):
        self._rec.pause()

    def stop(self):
        self._rec.stop()
        self._has_location = False
