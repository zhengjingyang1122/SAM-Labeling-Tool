from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

from modules.app.actions import Actions
from modules.infrastructure.devices.camera_manager import CameraManager
from modules.infrastructure.io.burst import BurstShooter
from modules.infrastructure.io.photo import PhotoCapture
from modules.infrastructure.io.recorder import VideoRecorder
from modules.infrastructure.logging.logging_setup import (
    get_logger,
    install_qt_message_proxy,
    install_ui_targets,
    setup_logging,
)
from modules.presentation.qt.explorer.explorer_controller import ExplorerController
from modules.presentation.qt.onboarding import OnboardingWizard
from modules.presentation.qt.shortcuts import get_app_shortcut_manager
from modules.presentation.qt.status_footer import StatusFooter
from modules.presentation.qt.ui_main import build_ui, wire_ui
from modules.presentation.qt.ui_state import update_ui_state

logger = logging.getLogger(__name__)


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

        log_p = "logs"
        lvl = "INFO"
        json_enabled = True
        max_bytes = 2000000
        backup_count = 5
        setup_logging(
            log_dir=log_p,
            level=lvl,
            json_enabled=json_enabled,
            max_bytes=max_bytes,
            backup_count=backup_count,
        )

        popup_lvl = logging.ERROR
        rate_ms = 1500
        install_ui_targets(self, self.status, rate_limit_ms=rate_ms, popup_level=popup_lvl)

        # 安裝 Qt 訊息代理, 使 Qt 警告也進入 logging
        install_qt_message_proxy()

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

        # 新增: 開啟日誌資料夾
        act_logs = QAction("開啟日誌資料夾", self)

        def _open_logs():
            p = Path("logs").expanduser()
            p.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

        act_logs.triggered.connect(_open_logs)

        m.addAction(act_tour)
        m.addAction(act_keys)
        m.addAction(act_logs)

    def _maybe_run_onboarding(self):
        pass

    def _show_onboarding(self, first_run: bool = False):
        try:
            wiz = OnboardingWizard(self)
            wiz.exec()
        except Exception as e:
            logger.warning("導覽載入失敗: %s", e, exc_info=True)
            QMessageBox.information(self, "導覽", f"導覽載入失敗: {e}")


def main():
    app = QApplication(sys.argv)

    # 捕捉未處理例外
    def _excepthook(exc_type, exc, tb):
        logger = get_logger("Uncaught")
        logger.error("Uncaught exception", exc_info=(exc_type, exc, tb))

    sys.excepthook = _excepthook

    w = MainWindow()
    w.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
