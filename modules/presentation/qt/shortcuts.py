# modules/presentation/qt/shortcuts.py
from __future__ import annotations

from typing import Callable, Dict, Iterable, Optional, Union

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
)

from modules.app.config_manager import config

KeySeqLike = Union[str, Iterable[str]]


def _to_list(v: KeySeqLike) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return [str(x) for x in v]


class ShortcutManager:
    def __init__(self) -> None:
        """Initializes the shortcut manager by loading shortcuts from the global config."""
        self._map: Dict[str, Dict[str, list[str]]] = {
            s: {k: _to_list(v) for k, v in d.items()}
            for s, d in config.get("shortcuts", {}).items()
        }
        self._created_actions: list[QAction] = []

    def sequences(self, scope: str, action_key: str) -> list[str]:
        return list(self._map.get(scope, {}).get(action_key, []))

    def bind(
        self, widget: QWidget, seqs: list[str], target: Union[QAction, Callable[[], None]]
    ) -> QAction:
        if isinstance(target, QAction):
            act = target
            act.setShortcuts([QKeySequence(s) for s in seqs])
            act.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            widget.addAction(act)
        else:
            act = QAction(widget)
            act.setShortcuts([QKeySequence(s) for s in seqs])
            act.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            act.triggered.connect(target)
            widget.addAction(act)
        self._created_actions.append(act)
        return act

    def clear_actions(self, widget: QWidget) -> None:
        # 移除所有先前註冊的 QAction。若 QAction 已被 Qt 刪除則忽略例外。
        for act in self._created_actions:
            try:
                widget.removeAction(act)
            except RuntimeError:
                # QAction 已經被刪除，不需要再移除
                pass
        self._created_actions.clear()

    def register_main(self, win: QWidget, actions) -> None:
        self.clear_actions(win)  # Clear existing actions before re-registering
        mapping: Dict[tuple[str, str], Union[QAction, Callable[[], None]]] = {
            ("main", "capture.photo"): actions.capture_image,
            ("main", "record.start_resume"): actions.resume_recording,
            ("main", "record.stop_save"): actions.stop_recording,
        }
        for (scope, key), tgt in mapping.items():
            seqs = self.sequences(scope, key)
            if seqs:
                self.bind(win, seqs, tgt)

    def register_viewer(self, viewer) -> None:
        self.clear_actions(viewer)  # Clear existing actions before re-registering
        mapping: Dict[tuple[str, str], Union[QAction, Callable[[], None]]] = {
            ("viewer", "nav.prev"): viewer._prev_image,
            ("viewer", "nav.next"): viewer._next_image,
            ("viewer", "save.selected"): viewer._save_selected,
            ("viewer", "save.union"): viewer.save_union_hotkey,
            ("viewer", "window.close"): viewer.close,
        }
        for (scope, key), tgt in mapping.items():
            seqs = self.sequences(scope, key)
            if seqs:
                self.bind(viewer, seqs, tgt)

    def show_shortcuts_dialog(self, parent: QWidget, win: QWidget, actions) -> None:
        rows = []
        for scope, table in self._map.items():
            for key, seqs in table.items():
                rows.append((scope, key, ", ".join(seqs)))
        rows.sort()

        dlg = QDialog(parent)
        dlg.setWindowTitle("快捷鍵一覽")
        table = QTableWidget(len(rows), 3, dlg)
        table.setHorizontalHeaderLabels(["Scope", "Action", "Keys"])
        for r, (scope, key, seq) in enumerate(rows):
            table.setItem(r, 0, QTableWidgetItem(scope))
            table.setItem(r, 1, QTableWidgetItem(key))
            table.setItem(r, 2, QTableWidgetItem(seq))
        table.resizeColumnsToContents()
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)  # Make table read-only

        btn_close = QPushButton("關閉", dlg)
        btn_close.clicked.connect(dlg.accept)

        lay = QVBoxLayout(dlg)
        lay.addWidget(table)
        hlay = QHBoxLayout()
        hlay.addStretch(1)
        hlay.addWidget(btn_close)
        lay.addLayout(hlay)

        dlg.resize(520, 360)
        dlg.exec()


def get_app_shortcut_manager() -> ShortcutManager:
    app = QApplication.instance()
    mgr = app.property("shortcut_manager")
    if not isinstance(mgr, ShortcutManager):
        mgr = ShortcutManager()
        app.setProperty("shortcut_manager", mgr)
    return mgr