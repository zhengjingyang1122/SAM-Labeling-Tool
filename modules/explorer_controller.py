# modules/explorer_controller.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QMainWindow, QPushButton

from modules.explorer import MediaExplorer


class ExplorerController:
    """封裝 Dock 建立、按鈕切換、可視狀態同步與重新指定根目錄"""

    def __init__(self, main_window: QMainWindow, toggle_btn: QPushButton, dir_edit: QLineEdit):
        self._win = main_window
        self._btn = toggle_btn
        self._dir_edit = dir_edit

        self.explorer = MediaExplorer(self._win)
        self._win.addDockWidget(Qt.LeftDockWidgetArea, self.explorer)
        self.set_root_dir_from_edit()

        self._btn.setCheckable(True)
        self._btn.setChecked(True)
        self._btn.toggled.connect(self._on_toggle)

        self.explorer.visibilityChanged.connect(self._on_visibility_changed)

    def _on_toggle(self, checked: bool):
        self.explorer.setVisible(checked)
        if checked:
            try:
                self.explorer.setFloating(False)
            except Exception:
                pass

    def _on_visibility_changed(self, visible: bool):
        self._btn.blockSignals(True)
        self._btn.setChecked(visible)
        self._btn.blockSignals(False)

    def set_root_dir_from_edit(self):
        path = Path(self._dir_edit.text()).expanduser()
        self.explorer.set_root_dir(path)

    def refresh(self):
        self.explorer.refresh()
