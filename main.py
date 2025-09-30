from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

from modules.actions import Actions
from modules.burst import BurstShooter
from modules.camera_manager import CameraManager
from modules.explorer_controller import ExplorerController
from modules.photo import PhotoCapture
from modules.prefs import get_prefs
from modules.recorder import VideoRecorder
from modules.shortcuts import get_app_shortcut_manager
from modules.status_footer import StatusFooter
from modules.ui_main import build_ui, wire_ui
from modules.ui_state import update_ui_state


class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle("Webcam Snapper - Modular Edition")
        self.resize(1100, 720)

        # Controllers (exposed for UI state checks)
        self.cam = CameraManager(self)
        self.photo_ctrl: Optional[PhotoCapture] = None
        self.burst_ctrl: Optional[BurstShooter] = None
        self.rec_ctrl: Optional[VideoRecorder] = None

        # Build UI (widgets & layout only)
        build_ui(self)

        self.status = StatusFooter.install(self)
        self.status.message("狀態：待機")

        # Left dock: file explorer controller
        self.explorer_ctrl = ExplorerController(self, self.btn_toggle_explorer, self.dir_edit)

        # Actions: all slots/logic are centralized here
        self.ui_actions = Actions(self, self.cam, self.explorer_ctrl)
        mgr = get_app_shortcut_manager()
        mgr.register_main(self, self.ui_actions, self.explorer_ctrl)
        wire_ui(self, self.ui_actions)

        # ✅ 加入全域樣式、快捷鍵、說明選單、首次導覽
        self._apply_global_style()
        self._install_help_menu()
        self._maybe_run_onboarding()

        # Initial state & device list
        update_ui_state(self)
        self.explorer_ctrl.refresh()
        self.ui_actions.populate_camera_devices()

        prefs = get_prefs()
        out_dir = prefs.get("output_dir", "")
        if out_dir:
            try:
                self.dir_edit.setText(out_dir)
                self.explorer_ctrl.set_root(out_dir)
            except Exception:
                pass

        # 相機偏好可在裝置掃描完成後套用
        # 假設 actions 或 camera_manager 有 refresh_devices()
        try:
            want = prefs.get("camera.preferred_device", "")
            if want:
                self.ui_actions.select_camera_by_name(want)  # 需在 Actions 補這個 helper, 見下方
        except Exception:
            pass
        self.dir_edit.editingFinished.connect(lambda: prefs.set("output_dir", self.dir_edit.text()))

    # 新增到 MainWindow 類別內
    def _apply_global_style(self):
        # 輕量現代化樣式表(Stylesheet), 不影響既有 SciFi 對話框
        self.setStyleSheet(
            """
        QWidget { font-size: 12px; }
        QGroupBox {
            margin-top: 10px; padding: 8px; border: 1px solid #3a3f47; border-radius: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin; subcontrol-position: top left; padding: 0 6px;
            color: #cfd8dc; font-weight: 600;
        }
        QPushButton {
            padding: 6px 10px; border: 1px solid #3a3f47; border-radius: 6px;
            background: #2b2f36; color: #e8eaed;
        }
        QPushButton:hover { background: #333844; }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            border: 1px solid #3a3f47; border-radius: 6px; padding: 4px 6px; background: #1b1e23; color: #e8eaed;
        }
        """
        )

    def _install_help_menu(self):
        m = self.menuBar().addMenu("說明")
        act_tour = QAction("快速導覽", self)
        act_tour.triggered.connect(self._show_onboarding)
        act_keys = QAction("鍵盤快捷鍵", self)

        def _show_keys():
            mgr = get_app_shortcut_manager()
            mgr.show_shortcuts_dialog(self)

        act_keys.triggered.connect(_show_keys)
        m.addAction(act_tour)
        m.addAction(act_keys)

    def _maybe_run_onboarding(self):
        s = QSettings("VersaLab", "WebcamSnapper")
        first = s.value("onboarded", False, type=bool) is False
        if first:
            self._show_onboarding(first_run=True)
            s.setValue("onboarded", True)

    def _show_onboarding(self, first_run: bool = False):
        try:
            from modules.onboarding import OnboardingWizard

            wiz = OnboardingWizard(self)
            wiz.exec()
        except Exception as e:
            QMessageBox.information(self, "導覽", f"導覽載入失敗: {e}")


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
