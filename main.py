from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtWidgets import QApplication, QMainWindow

from modules.actions import Actions
from modules.burst import BurstShooter
from modules.camera_manager import CameraManager
from modules.explorer_controller import ExplorerController
from modules.photo import PhotoCapture
from modules.recorder import VideoRecorder
from modules.ui_main import build_ui, wire_ui
from modules.ui_state import update_ui_state


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Webcam Snapper - Modular Edition")
        self.resize(1100, 720)

        # Controllers (exposed for UI state checks)
        self.cam = CameraManager(self)
        self.photo_ctrl: Optional[PhotoCapture] = None
        self.burst_ctrl: Optional[BurstShooter] = None
        self.rec_ctrl: Optional[VideoRecorder] = None

        # Build UI (widgets & layout only)
        build_ui(self)

        # Left dock: file explorer controller
        self.explorer_ctrl = ExplorerController(self, self.btn_toggle_explorer, self.dir_edit)

        # Actions: all slots/logic are centralized here
        self.ui_actions = Actions(self, self.cam, self.explorer_ctrl)
        wire_ui(self, self.ui_actions)

        # Initial state & device list
        update_ui_state(self)
        self.explorer_ctrl.refresh()
        self.ui_actions.populate_camera_devices()


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
