# modules/onboarding.py
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWizard, QWizardPage


class OnboardingWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("快速導覽")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        # Page 1: 歡迎
        p1 = QWizardPage()
        p1.setTitle("歡迎使用 Webcam Snapper")
        lay1 = QVBoxLayout(p1)
        lay1.addWidget(
            QLabel("這是一款整合拍照、連拍、錄影與自動分割的應用.\n\n接下來用 1 分鐘快速熟悉介面.")
        )

        # Page 2: 基本操作
        p2 = QWizardPage()
        p2.setTitle("相機與拍照")
        lay2 = QVBoxLayout(p2)
        lay2.addWidget(
            QLabel(
                "1. 在『相機設備』選擇裝置並點『啟動相機』.\n2. 用『拍一張』或使用 Space 進行拍照.\n3. 輸出路徑可在右上方『輸出路徑』設定."
            )
        )

        # Page 3: 進階功能
        p3 = QWizardPage()
        p3.setTitle("連拍、錄影與自動分割")
        lay3 = QVBoxLayout(p3)
        lay3.addWidget(
            QLabel(
                "• 連拍: 設定張數與間隔後按『開始連拍』.\n• 錄影: 按『開始/繼續』與『停止』, R 也能開始/繼續.\n• 自動分割: 點『自動分割影像』開啟選單."
            )
        )

        # Page 4: 小技巧
        p4 = QWizardPage()
        p4.setTitle("小技巧與說明")
        lay4 = QVBoxLayout(p4)
        lay4.addWidget(
            QLabel(
                "• 左側『媒體檔案』可瀏覽與管理輸出.\n• 狀態列會顯示進度與即時提示.\n• 任何時候可從『說明 > 快速導覽』再看一次."
            )
        )

        self.addPage(p1)
        self.addPage(p2)
        self.addPage(p3)
        self.addPage(p4)
