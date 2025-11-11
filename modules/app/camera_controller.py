"""Camera controller for the SAM‑Labeling‑Tool.

This controller encapsulates all camera related behaviours such as
listing devices, selecting a device, starting/stopping the camera,
capturing images, starting/stopping bursts and controlling recording.

The intent of this controller is to improve cohesion by grouping
related camera logic in one place, while reducing coupling by hiding
the underlying camera manager and UI details from the rest of the
application. The controller accepts a reference to the main window
(``win``) and a ``CameraManager`` instance. It uses the window to
update user interface elements like the status bar and directory
inputs, but the higher level ``Actions`` class delegates all camera
work to this controller.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QMessageBox

from modules.app.config_manager import config
from modules.infrastructure.devices.camera_manager import CameraManager
from utils.utils import clear_current_path_manager
from modules.presentation.qt.ui_state import update_ui_state


logger = logging.getLogger(__name__)


class CameraController:
    """Encapsulate camera related behaviours.

    Parameters
    ----------
    win : object
        The main window or widget that provides access to UI elements
        such as the camera combo box, directory edit and status footer.
    cam : CameraManager
        The underlying camera manager responsible for interacting with
        the system's camera hardware.
    """

    def __init__(self, win: object, cam: CameraManager) -> None:
        self.w = win
        self.cam = cam

    # ------------------------------------------------------------------
    # Device selection
    # ------------------------------------------------------------------
    def select_camera_by_name(self, name: str) -> None:
        """Select a camera device by its display name.

        This helper iterates through the items in the camera combo box
        and sets the current index when a matching name is found. It
        swallows all exceptions to avoid interrupting the UI flow.
        """
        try:
            cb = self.w.cam_combo
            for i in range(cb.count()):
                if cb.itemText(i) == name:
                    cb.setCurrentIndex(i)
                    break
        except Exception:
            # quietly ignore errors – failing to select a camera by name
            # should not crash the application
            pass

    def populate_camera_devices(self) -> None:
        """Populate the camera combo box with available devices.

        This method queries the ``CameraManager`` for a list of devices
        and converts them into strings and user data suitable for a
        ``QComboBox``. Any exceptions are caught and presented to the
        user via a message box.
        """
        try:
            self.w.cam_combo.clear()
            try:
                devices = list(self.cam.list_devices())
            except Exception:
                devices = []
            for item in devices:
                text = None
                userData = None
                # Support tuple/list, dict or other types from list_devices()
                if isinstance(item, (tuple, list)):
                    str_elems = [x for x in item if isinstance(x, str)]
                    int_elems = [x for x in item if isinstance(x, int)]
                    if str_elems:
                        text = str_elems[0]
                        userData = int_elems[0] if int_elems else tuple(item)
                    else:
                        text = " / ".join(str(x) for x in item)
                        userData = tuple(item)
                elif isinstance(item, dict):
                    text = str(
                        item.get("name")
                        or item.get("label")
                        or item.get("path")
                        or item.get("id")
                        or "device"
                    )
                    userData = item.get("id", item.get("index", item))
                else:
                    text = str(item)
                    userData = item
                self.w.cam_combo.addItem(text, userData)
            if self.w.cam_combo.count() > 0:
                self.w.cam_combo.setCurrentIndex(0)
        except Exception as e:
            QMessageBox.critical(self.w, "讀取裝置失敗", str(e))

    # ------------------------------------------------------------------
    # Camera start/stop
    # ------------------------------------------------------------------
    def start_camera(self) -> None:
        """Start the camera preview and initialise control objects.

        On success, the status bar is updated and the UI state is
        refreshed. On failure, an error message is shown.
        """
        try:
            data = self.w.cam_combo.currentData()
            idx = data if isinstance(data, int) else self.w.cam_combo.currentIndex()
            try:
                self.cam.set_selected_device_index(idx)
            except Exception:
                # ignore invalid indices; the camera manager will fall back
                pass
            # Start camera and preview
            self.cam.start(self.w.video_widget)
            self.w.status.message("狀態: 相機啟動")
            update_ui_state(self.w)
        except Exception as e:
            QMessageBox.critical(self.w, "相機啟動失敗", str(e))

    def stop_camera(self) -> None:
        """Stop the camera preview and reset UI state."""
        try:
            self.cam.stop()
            # Clear the preview widget to a black background
            self.w.video_widget.setStyleSheet("background-color: black;")
            self.w.video_widget.update()
            self.w.status.message("狀態：相機停止")
            update_ui_state(self.w)
        except Exception as e:
            QMessageBox.critical(self.w, "相機停止失敗", str(e))

    # ------------------------------------------------------------------
    # Photo capture
    # ------------------------------------------------------------------
    def capture_image(self) -> None:
        """Capture a single photo to the output directory."""
        clear_current_path_manager()
        out_dir = Path(self.w.dir_edit.text())
        if getattr(self.cam, "photo", None) is None:
            QMessageBox.warning(self.w, "無法拍照", "相機尚未啟動或不支援拍照")
            return
        try:
            self.cam.photo.capture_single(out_dir)
            self.w.status.message("狀態：已拍照")
        except Exception as e:
            logger.exception("拍照失敗")
            QMessageBox.critical(self.w, "拍照失敗", str(e))

    # ------------------------------------------------------------------
    # Burst capture
    # ------------------------------------------------------------------
    def start_burst(self) -> None:
        """Start a burst photo capture session."""
        if getattr(self.cam, "burst", None) is None:
            QMessageBox.warning(self.w, "無法連拍", "相機尚未啟動或不支援連拍")
            return
        clear_current_path_manager()
        out_dir = Path(self.w.dir_edit.text())
        count = int(self.w.burst_count.value())
        interval = int(self.w.burst_interval.value())
        self.cam.burst.start(count, interval, out_dir)
        # Hold a reference on the window for later pause/stop
        self.w.burst_ctrl = self.cam.burst
        update_ui_state(self.w)

    def stop_burst(self) -> None:
        """Stop an ongoing burst session."""
        if getattr(self.cam, "burst", None):
            self.cam.burst.stop()
        self.w.burst_ctrl = None
        update_ui_state(self.w)

    # ------------------------------------------------------------------
    # Recording control
    # ------------------------------------------------------------------
    def resume_recording(self) -> None:
        """Start or resume a video recording session."""
        clear_current_path_manager()
        out_dir = Path(self.w.dir_edit.text())
        if getattr(self.cam, "rec", None) is None:
            logger.warning("錄影控制器不存在或相機未啟動")
            QMessageBox.warning(self.w, "無法錄影", "相機尚未啟動或不支援錄影")
            return
        self.cam.rec.start_or_resume(out_dir)
        self.w.rec_ctrl = self.cam.rec
        self.w.status.message("狀態：錄影中")

    def pause_recording(self) -> None:
        """Pause the current recording if one is active."""
        if getattr(self.w, "rec_ctrl", None) is None:
            return
        try:
            self.w.rec_ctrl.pause()
            self.w.status.message("狀態：錄影暫停")
        except Exception as e:
            QMessageBox.critical(self.w, "暫停錄影錯誤", str(e))

    def stop_recording(self) -> None:
        """Stop the current recording if one is active."""
        if getattr(self.w, "rec_ctrl", None) is None:
            return
        try:
            self.w.rec_ctrl.stop()
            self.w.status.message("狀態：錄影停止")
        except Exception as e:
            logger.exception("停止錄影錯誤")
            QMessageBox.critical(self.w, "停止錄影錯誤", str(e))