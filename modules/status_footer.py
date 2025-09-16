# modules/status_footer.py
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)


class StatusFooter(QStatusBar):
    """統一美化的底部狀態列：訊息 + 進度（支援忙碌/不定進度 與 定量進度）"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("UnifiedStatusFooter")

        # 文字 + 進度
        self._msg = QLabel("準備就緒", self)
        self._msg.setObjectName("StatusMessageLabel")
        self._msg.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._progress = QProgressBar(self)
        self._progress.setObjectName("StatusProgressBar")
        self._progress.setFixedHeight(14)
        self._progress.setVisible(False)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)

        wrap = QWidget(self)
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(10)
        lay.addWidget(self._msg, 1)
        lay.addWidget(self._progress, 0)
        self.addPermanentWidget(wrap, 1)

        # style
        self.setStyleSheet(
            """
#UnifiedStatusFooter {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #2b2f36, stop:1 #22252b);
    color: #e8eaed;
    border-top: 1px solid #3a3f47;
    font-size: 12px;
}
#StatusMessageLabel {
    color: #e8eaed;
}
#StatusProgressBar {
    background: #1b1e23;
    border: 1px solid #3a3f47;
    border-radius: 7px;
}
#StatusProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #00b894, stop:1 #00cec9);
    border-radius: 6px;
}
"""
        )

        # 暫時訊息
        self._last_persist_msg = "準備就緒"
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_temp_timeout)

        # 科幻彈窗指標
        self._scifi: Optional[SciFiProgressDialog] = None

    # ---------- 公開 API ----------
    def message(self, text: str) -> None:
        self._last_persist_msg = text
        self._msg.setText(text)

    def message_temp(self, text: str, ms: int = 2500) -> None:
        self._msg.setText(text)
        self._timer.start(max(1, int(ms)))

    def start_busy(self, text: Optional[str] = None) -> None:
        if text:
            self.message(text)
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)

    def stop_busy(self, text: Optional[str] = None) -> None:
        self._progress.setVisible(False)
        self._progress.setRange(0, 100)
        if text is not None:
            self.message(text)

    def set_progress(self, value: int, text: Optional[str] = None, maximum: int = 100) -> None:
        self._progress.setVisible(True)
        self._progress.setRange(0, max(1, int(maximum)))
        v = max(0, min(int(value), self._progress.maximum()))
        self._progress.setValue(v)
        if text:
            self.message(text)

    # ---------- 靜態安裝器 ----------
    @staticmethod
    def install(win: QMainWindow) -> "StatusFooter":
        bar = StatusFooter(win)
        win.setStatusBar(bar)
        return bar

    # ---------- 內部 ----------
    def _on_temp_timeout(self):
        self._msg.setText(self._last_persist_msg)

    # ---------- 科幻進度條 API ----------
    def start_scifi(self, text: str = "處理中...") -> None:
        try:
            if self._scifi is None:
                self._scifi = SciFiProgressDialog(parent=self.parent(), title=text)
            else:
                self._scifi.set_title(text)
            self._scifi.center_to_parent()
            self._scifi.show()
            self._scifi.raise_()

            # ★ 新增：顯示後立刻處理一次事件，確保視窗真的畫出來
            from PySide6.QtGui import QGuiApplication

            QGuiApplication.processEvents()
        except Exception:
            self.start_busy(text)

    def set_scifi_progress(self, value: int, text: Optional[str] = None) -> None:
        if self._scifi is None:
            self.start_scifi(text or "處理中...")
        if text:
            self._scifi.set_title(text)
        self._scifi.set_determinate(value)

        # ★ 新增：更新進度後也刷新一次，避免卡在重計算時看不到變化
        from PySide6.QtGui import QGuiApplication

        QGuiApplication.processEvents()

    def stop_scifi(self, text: Optional[str] = None) -> None:
        try:
            if self._scifi:
                self._scifi.close()

                # ★ 新增：關閉後刷一次，馬上恢復底部狀態訊息
                from PySide6.QtGui import QGuiApplication

                QGuiApplication.processEvents()
        finally:
            self._scifi = None
            if text is not None:
                self.message(text)


# ========== 科幻進度條對話框 ==========
class SciFiProgressDialog(QDialog):
    """半透明霓虹風掃描條 + 光暈"""

    def __init__(self, parent=None, title: str = "處理中..."):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)

        self._title_label = QLabel(title, self)
        self._bar = QProgressBar(self)
        self._bar.setRange(0, 0)  # 預設不定進度
        self._bar.setTextVisible(False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.addWidget(self._title_label)
        lay.addWidget(self._bar)

        # 霓虹樣式
        self.setStyleSheet(
            """
QDialog {
    background: rgba(7, 12, 20, 180);
    border: 1px solid rgba(0, 200, 255, 160);
    border-radius: 12px;
}
QLabel {
    color: #bffaff;
    font-size: 14px;
    letter-spacing: 1px;
}
QProgressBar {
    border: 1px solid rgba(0, 200, 255, 140);
    border-radius: 8px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 rgba(0,40,60,220), stop:1 rgba(0,25,45,220));
    height: 16px;
}
QProgressBar::chunk {
    border-radius: 7px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #00e5ff, stop:0.5 #00ffd5, stop:1 #00e5ff);
}
"""
        )

        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(40)
        glow.setOffset(0, 0)
        glow.setColor(Qt.cyan)
        self._bar.setGraphicsEffect(glow)

        # 不定進度掃描動畫（來回 0↔100）
        self._indeterminate = True
        self._t = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # 約 60 fps

    def _tick(self):
        if self._indeterminate:
            self._t = (self._t + 2) % 200
            v = self._t if self._t <= 100 else 200 - self._t
            self._bar.setValue(v)

    def center_to_parent(self):
        if self.parent() and self.parent().isVisible():
            pw, ph = self.parent().width(), self.parent().height()
            px, py = self.parent().x(), self.parent().y()
            self.resize(max(360, int(pw * 0.38)), 110)
            self.move(px + (pw - self.width()) // 2, py + (ph - self.height()) // 2)
        else:
            screen = QGuiApplication.primaryScreen().geometry()
            self.resize(420, 110)
            self.move(screen.center() - self.rect().center())

    def set_title(self, text: str):
        self._title_label.setText(text)

    def set_determinate(self, value: int):
        self._indeterminate = False
        self._bar.setRange(0, 100)
        self._bar.setValue(max(0, min(100, int(value))))
