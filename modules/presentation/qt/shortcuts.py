# modules/shortcuts.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Tuple, Union

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

KeySeqLike = Union[str, Iterable[str]]

DEFAULT_SHORTCUTS: Dict[str, Dict[str, KeySeqLike]] = {
    "main": {
        "capture.photo": "Space",
        "record.start_resume": "R",
        "record.stop_save": "Shift+R",
    },
    "viewer": {
        "nav.prev": ["Left", "PageUp"],
        "nav.next": ["Right", "PageDown"],
        "save.selected": ["S", "Ctrl+S"],
        "save.union": "U",
        "window.close": "Esc",
    },
}


def _to_list(v: KeySeqLike) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return [str(x) for x in v]


class ShortcutManager:
    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config_path = Path(config_path) if config_path else Path("config/shortcuts.json")
        self._map: Dict[str, Dict[str, list[str]]] = {
            s: {k: _to_list(v) for k, v in d.items()} for s, d in DEFAULT_SHORTCUTS.items()
        }
        self._created_actions: list[QAction] = []
        self.load()

    def load(self) -> None:
        try:
            if self.config_path.exists():
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                for scope, table in (data or {}).items():
                    for action_key, seqs in (table or {}).items():
                        self._map.setdefault(scope, {})[action_key] = _to_list(seqs)
        except Exception:
            pass

    def save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        out = {s: {k: v for k, v in d.items()} for s, d in self._map.items()}
        self.config_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

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
        for act in self._created_actions:
            widget.removeAction(act)
        self._created_actions.clear()

    def register_main(self, win: QWidget, actions) -> None:
        self.clear_actions(win) # Clear existing actions before re-registering
        mapping: Dict[Tuple[str, str], Union[QAction, Callable[[], None]]] = {
            ("main", "capture.photo"): actions.capture_image,
            ("main", "record.start_resume"): actions.resume_recording,
            ("main", "record.stop_save"): actions.stop_recording,
        }
        for (scope, key), tgt in mapping.items():
            seqs = self.sequences(scope, key)
            if seqs:
                self.bind(win, seqs, tgt)

    def register_viewer(self, viewer) -> None:
        self.clear_actions(viewer) # Clear existing actions before re-registering
        mapping: Dict[Tuple[str, str], Union[QAction, Callable[[], None]]] = {
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

        def _edit_shortcut(row, column):
            if column != 2: # Only edit the 'Keys' column
                return

            scope = table.item(row, 0).text()
            key = table.item(row, 1).text()
            old_seq = table.item(row, 2).text()

            new_seq, ok = KeyCaptureDialog.get_key_sequence(dlg)
            if ok:
                table.item(row, 2).setText(new_seq)

        table.cellDoubleClicked.connect(_edit_shortcut)

        btn_save = QPushButton("儲存", dlg)

        def _save_shortcuts():
            for r in range(table.rowCount()):
                scope = table.item(r, 0).text()
                key = table.item(r, 1).text()
                seqs = table.item(r, 2).text().split(", ")
                self._map[scope][key] = [s.strip() for s in seqs if s.strip()]
            self.save()
            # Re-register the main shortcuts
            self.register_main(win, actions)
            dlg.accept()

        btn_save.clicked.connect(_save_shortcuts)

        btn_close = QPushButton("關閉", dlg)
        btn_close.clicked.connect(dlg.accept)

        lay = QVBoxLayout(dlg)
        lay.addWidget(table)
        hlay = QHBoxLayout()
        hlay.addStretch(1)
        hlay.addWidget(btn_save)
        hlay.addWidget(btn_close)
        lay.addLayout(hlay)

        dlg.resize(520, 360)
        dlg.exec()


class KeyCaptureDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("捕獲快捷鍵")
        self.layout = QVBoxLayout(self)
        self.label = QLabel("請按下您想設定的快捷鍵組合...")
        self.layout.addWidget(self.label)
        self.key_sequence = ""

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        if modifiers & Qt.ControlModifier:
            self.key_sequence += "Ctrl+"
        if modifiers & Qt.AltModifier:
            self.key_sequence += "Alt+"
        if modifiers & Qt.ShiftModifier:
            self.key_sequence += "Shift+"

        if key in range(Qt.Key_F1, Qt.Key_F12 + 1):
            self.key_sequence += f"F{key - Qt.Key_F1 + 1}"
        elif key == Qt.Key_Space:
            self.key_sequence += "Space"
        else:
            self.key_sequence += QKeySequence(key).toString()

        QTimer.singleShot(0, self.accept)

    @staticmethod
    def get_key_sequence(parent):
        dialog = KeyCaptureDialog(parent)
        result = dialog.exec()
        if result == QDialog.Accepted:
            return dialog.key_sequence, True
        return "", False


def get_app_shortcut_manager() -> ShortcutManager:
    app = QApplication.instance()
    mgr = app.property("shortcut_manager")
    if not isinstance(mgr, ShortcutManager):
        mgr = ShortcutManager()
        app.setProperty("shortcut_manager", mgr)
    return mgr
