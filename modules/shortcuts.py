# modules/shortcuts.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Tuple, Union

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
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
        "dock.toggle": "F9",
    },
    "viewer": {
        "nav.prev": ["Left", "PageUp"],
        "nav.next": ["Right", "PageDown"],
        "save.selected": ["S", "Ctrl+S"],
        "save.union": "U",
        "dock.toggle": "F9",
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

    # ---------- load/save ----------
    def load(self) -> None:
        try:
            if self.config_path.exists():
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                for scope, table in (data or {}).items():
                    for action_key, seqs in (table or {}).items():
                        self._map.setdefault(scope, {})[action_key] = _to_list(seqs)
        except Exception:
            # 若使用者 JSON 壞掉，忽略以免整體掛掉
            pass

    def save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        out = {s: {k: v for k, v in d.items()} for s, d in self._map.items()}
        self.config_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---------- public API ----------
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

    def register_main(self, win: QWidget, actions, explorer_ctrl) -> None:
        mapping: Dict[Tuple[str, str], Union[QAction, Callable[[], None]]] = {
            ("main", "capture.photo"): actions.capture_image,
            ("main", "record.start_resume"): actions.resume_recording,
            ("main", "record.stop_save"): actions.stop_recording,
            ("main", "dock.toggle"): explorer_ctrl.explorer.toggleViewAction(),  # QAction
        }
        for (scope, key), tgt in mapping.items():
            seqs = self.sequences(scope, key)
            if seqs:
                self.bind(win, seqs, tgt)

    def register_viewer(self, viewer) -> None:
        # viewer 需具備 act_toggle_dock 這個 QAction
        mapping: Dict[Tuple[str, str], Union[QAction, Callable[[], None]]] = {
            ("viewer", "nav.prev"): viewer._prev_image,
            ("viewer", "nav.next"): viewer._next_image,
            ("viewer", "save.selected"): viewer._save_selected,
            ("viewer", "save.union"): viewer._save_union,
            ("viewer", "dock.toggle"): viewer.act_toggle_dock,  # QAction
            ("viewer", "window.close"): viewer.close,
        }
        for (scope, key), tgt in mapping.items():
            seqs = self.sequences(scope, key)
            if seqs:
                self.bind(viewer, seqs, tgt)

    def show_shortcuts_dialog(self, parent: QWidget) -> None:
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

        btn = QPushButton("關閉", dlg)
        btn.clicked.connect(dlg.accept)

        lay = QVBoxLayout(dlg)
        lay.addWidget(table)
        lay.addWidget(btn)
        dlg.resize(520, 360)
        dlg.exec()


def get_app_shortcut_manager() -> ShortcutManager:
    app = QApplication.instance()
    mgr = app.property("shortcut_manager")
    if not isinstance(mgr, ShortcutManager):
        mgr = ShortcutManager()
        app.setProperty("shortcut_manager", mgr)
    return mgr
