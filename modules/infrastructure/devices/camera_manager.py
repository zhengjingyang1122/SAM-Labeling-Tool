# modules/camera_manager.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

import cv2  # ← 新增

# 建議放在檔頭
import numpy as np  # ← 新增

# 既有 import 區段中補上：
from PySide6.QtCore import QObject, QTimer, Signal  # ← 新增 Signal
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QVideoSink  # ← 新增
from PySide6.QtMultimedia import (
    QAudioInput,
    QCamera,
    QCameraDevice,
    QImageCapture,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaFormat,
    QMediaRecorder,
)
from PySide6.QtMultimediaWidgets import QVideoWidget

from modules.infrastructure.io.burst import BurstShooter
from modules.infrastructure.io.photo import PhotoCapture
from modules.infrastructure.io.recorder import VideoRecorder

from PySide6.QtMultimedia import QVideoFrame

logger = logging.getLogger(__name__)


class CameraManager(QObject):
    """封裝相機裝置清單、啟停、Session 與控制器建置"""
    focusUpdated = Signal(float, bool)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._camera: Optional[QCamera] = None
        self._session: Optional[QMediaCaptureSession] = None
        self._image: Optional[QImageCapture] = None
        self._recorder: Optional[QMediaRecorder] = None
        self._audio: Optional[QAudioInput] = None
        self._selected: Optional[QCameraDevice] = None

        self._focus_threshold: float = 120.0
        self._frame_counter: int = 0

        # 封裝後對外提供的控制器
        self.photo: Optional[PhotoCapture] = None
        self.burst: Optional[BurstShooter] = None
        self.rec: Optional[VideoRecorder] = None

    def _on_focus_score_calculated(self, score: float):
        """接收來自 Sink 的原始分數, 判斷後對外發射最終訊號"""
        if score < 1.0:  # 過濾掉純黑畫面等無效分數
            return
        is_sharp = score >= self._focus_threshold
        self.focusUpdated.emit(score, is_sharp)

    def set_focus_threshold(self, value: float):
        self._focus_threshold = max(0, float(value))

    def get_focus_threshold(self) -> float:
        return self._focus_threshold

    def _process_frame(self, frame: QVideoFrame):
        """此方法在 videoSink().videoFrameChanged 訊號觸發時執行"""
        try:
            self._frame_counter += 1
            if self._frame_counter % 5 != 0:  # 每 5 幀評估一次以降低負載
                return

            if not frame.isValid() or frame.size().isEmpty():
                return

            img = frame.toImage()
            if img.isNull():
                return

            if img.format() != QImage.Format.Format_Grayscale8:
                img = img.convertToFormat(QImage.Format.Format_Grayscale8)

            ptr = img.constBits()
            arr = np.frombuffer(ptr, np.uint8).reshape(img.height(), img.bytesPerLine())[:, :img.width()]

            score = float(cv2.Laplacian(arr, cv2.CV_64F).var())

            self._on_focus_score_calculated(score)

        except Exception:
            logger.debug("Frame processing for focus score failed", exc_info=True)

    # ---- 裝置清單 ----
    def list_devices(self) -> list[tuple[str, QCameraDevice]]:
        devs = list(QMediaDevices.videoInputs())
        out = []
        for i, d in enumerate(devs):
            try:
                name = d.description()
            except Exception:
                name = f"Camera {i}"
            out.append((name, d))
        return out

    def set_selected_device_index(self, idx: int):
        devs = list(QMediaDevices.videoInputs())
        self._selected = devs[idx] if 0 <= idx < len(devs) else None

    # ---- 啟停 ----
    def start(
        self,
        video_widget: QVideoWidget,
        on_image_saved: Optional[Callable[[int, str], None]] = None,
        on_image_error: Optional[Callable[[int, int, str], None]] = None,
        on_rec_state_changed: Optional[Callable[[int], None]] = None,
        on_rec_error: Optional[Callable[[int, str], None]] = None,
    ):
        if self._camera is not None:
            logger.info("Camera already active, skip start()")
            return

        dev = self._selected or QMediaDevices.defaultVideoInput()
        self._camera = QCamera(dev)
        self._session = QMediaCaptureSession()
        self._session.setCamera(self._camera)

        # 1. 設定 UI 顯示
        self._session.setVideoOutput(video_widget)

        # 2. 連接影像幀處理
        sink = video_widget.videoSink()
        if sink:
            sink.videoFrameChanged.connect(self._process_frame)
        else:
            logger.warning("無法從 QVideoWidget 取得 videoSink，對焦計算功能將被停用。")

        self._image = QImageCapture()
        self._session.setImageCapture(self._image)

        # 註冊影像訊號
        if on_image_saved:
            self._image.imageSaved.connect(on_image_saved)
        if on_image_error:
            self._image.errorOccurred.connect(on_image_error)

        self._audio = QAudioInput(QMediaDevices.defaultAudioInput())
        self._session.setAudioInput(self._audio)

        self._recorder = QMediaRecorder()
        self._session.setRecorder(self._recorder)

        # 媒體格式（盡力）
        try:
            fmt = QMediaFormat()
            fmt.setFileFormat(QMediaFormat.MPEG4)
            fmt.setVideoCodec(QMediaFormat.VideoCodec.H264)
            fmt.setAudioCodec(QMediaFormat.AudioCodec.AAC)
            self._recorder.setMediaFormat(fmt)
            self._recorder.setQuality(QMediaRecorder.Quality.NormalQuality)
        except Exception:
            logger.warning("Recorder media format not fully set", exc_info=True)

        # 註冊錄影訊號
        if on_rec_state_changed:
            self._recorder.recorderStateChanged.connect(on_rec_state_changed)
        if on_rec_error:
            self._recorder.errorChanged.connect(on_rec_error)

        # 建立控制器
        self.photo = PhotoCapture(self._image, parent=self)
        self.burst = BurstShooter(self._image, parent=self)
        self.rec = VideoRecorder(self._recorder, parent=self)

        try:
            self._camera.start()
            logger.info("Camera started")
        except Exception:
            logger.exception("Camera start failed")
            raise

    def stop(self):
        # 先停止 recorder 與 camera
        try:
            if self.rec:
                self.rec.stop()
        except Exception:
            logger.warning("Recorder stop raised exception", exc_info=True)
        try:
            if self._camera:
                self._camera.stop()
        except Exception:
            logger.warning("Camera stop raised exception", exc_info=True)

        # 清理
        self.photo = None
        self.burst = None
        self.rec = None
        self._image = None
        self._recorder = None
        self._audio = None
        self._session = None
        self._camera = None

    # ---- 狀態 ----
    def is_active(self) -> bool:
        if not self._camera:
            return False
        try:
            return self._camera.isActive()
        except Exception:
            from PySide6.QtMultimedia import QCamera as _QCam

            return self._camera.cameraState() == _QCam.ActiveState


