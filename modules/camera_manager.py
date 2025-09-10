# modules/camera_manager.py
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject
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

from modules.burst import BurstShooter
from modules.photo import PhotoCapture
from modules.recorder import VideoRecorder


class CameraManager(QObject):
    """封裝相機裝置清單、啟停、Session 與控制器建置"""

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._camera: Optional[QCamera] = None
        self._session: Optional[QMediaCaptureSession] = None
        self._image: Optional[QImageCapture] = None
        self._recorder: Optional[QMediaRecorder] = None
        self._audio: Optional[QAudioInput] = None
        self._selected: Optional[QCameraDevice] = None

        # 封裝後對外提供的控制器
        self.photo: Optional[PhotoCapture] = None
        self.burst: Optional[BurstShooter] = None
        self.rec: Optional[VideoRecorder] = None

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
            return

        dev = self._selected or QMediaDevices.defaultVideoInput()
        self._camera = QCamera(dev)
        self._session = QMediaCaptureSession()
        self._session.setCamera(self._camera)

        self._session.setVideoOutput(video_widget)

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
            pass

        # 註冊錄影訊號
        if on_rec_state_changed:
            self._recorder.recorderStateChanged.connect(on_rec_state_changed)
        if on_rec_error:
            self._recorder.errorChanged.connect(on_rec_error)

        # 建立控制器
        self.photo = PhotoCapture(self._image, parent=self)
        self.burst = BurstShooter(self._image, parent=self)
        self.rec = VideoRecorder(self._recorder, parent=self)

        self._camera.start()

    def stop(self):
        # 先停止 recorder 與 camera
        try:
            if self.rec:
                self.rec.stop()
        except Exception:
            pass
        try:
            if self._camera:
                self._camera.stop()
        except Exception:
            pass

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
