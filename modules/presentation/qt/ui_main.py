# modules/ui_main.py
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QDockWidget,
    QStackedLayout,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence


def build_ui(win):
    """建立所有 UI 元件並掛到 win 上（不連接事件）"""
    central = QWidget(win)
    win.setCentralWidget(central)

    # 視訊預覽
    win.video_widget = QVideoWidget(win)
    win.video_widget.setMinimumSize(QSize(640, 360))

    # 輸出路徑
    dir_box = QGroupBox("輸出路徑")
    win.dir_edit = QLineEdit(str((Path.home() / "Pictures").expanduser()))
    win.btn_browse = QPushButton("瀏覽")
    dir_layout = QHBoxLayout()
    dir_layout.addWidget(QLabel("資料夾:"))
    dir_layout.addWidget(win.dir_edit, 1)
    dir_layout.addWidget(win.btn_browse)
    dir_box.setLayout(dir_layout)

    # 相機設備
    cam_sel_box = QGroupBox("相機設備")
    win.cam_combo = QComboBox()
    win.btn_refresh_cam = QPushButton("刷新設備")
    cam_sel_layout = QHBoxLayout()
    cam_sel_layout.addWidget(QLabel("裝置:"))
    cam_sel_layout.addWidget(win.cam_combo, 1)
    cam_sel_layout.addWidget(win.btn_refresh_cam)
    cam_sel_box.setLayout(cam_sel_layout)

    # 相機控制
    cam_box = QGroupBox("相機")
    win.btn_start_cam = QPushButton("啟動相機")
    win.btn_stop_cam = QPushButton("停止相機")
    cam_layout = QHBoxLayout()
    cam_layout.addWidget(win.btn_start_cam)
    cam_layout.addWidget(win.btn_stop_cam)
    cam_box.setLayout(cam_layout)

    # 一般拍照
    photo_box = QGroupBox("一般拍照")
    win.btn_capture = QPushButton("拍一張")
    photo_layout = QHBoxLayout()
    photo_layout.addWidget(win.btn_capture)
    photo_box.setLayout(photo_layout)

    # 連拍
    burst_box = QGroupBox("連拍")
    win.burst_count = QSpinBox()
    win.burst_count.setRange(1, 999)
    win.burst_count.setValue(5)
    win.burst_interval = QSpinBox()
    win.burst_interval.setRange(50, 10_000)
    win.burst_interval.setSingleStep(50)
    win.burst_interval.setValue(500)
    win.btn_start_burst = QPushButton("開始連拍")
    win.btn_stop_burst = QPushButton("停止連拍")
    burst_form = QFormLayout()
    burst_form.addRow("張數:", win.burst_count)
    burst_form.addRow("間隔(ms):", win.burst_interval)
    burst_btns = QHBoxLayout()
    burst_btns.addWidget(win.btn_start_burst)
    burst_btns.addWidget(win.btn_stop_burst)
    burst_layout = QVBoxLayout()
    burst_layout.addLayout(burst_form)
    burst_layout.addLayout(burst_btns)
    burst_box.setLayout(burst_layout)

    # 錄影
    rec_box = QGroupBox("錄影")
    win.btn_rec_resume = QPushButton("開始/繼續")
    win.btn_rec_pause = QPushButton("暫停")
    win.btn_rec_stop = QPushButton("停止")
    rec_layout = QHBoxLayout()
    rec_layout.addWidget(win.btn_rec_resume)
    rec_layout.addWidget(win.btn_rec_pause)
    rec_layout.addWidget(win.btn_rec_stop)
    rec_box.setLayout(rec_layout)

    # 右側
    right_panel = QVBoxLayout()
    right_panel.addWidget(dir_box)
    right_panel.addWidget(cam_sel_box)
    right_panel.addWidget(cam_box)
    right_panel.addWidget(photo_box)
    right_panel.addWidget(burst_box)
    right_panel.addWidget(rec_box)
    win.chk_preload_sam = QCheckBox("預先載入 SAM 模型")
    right_panel.addWidget(win.chk_preload_sam)
    seg_box = QGroupBox("分割工具")
    seg_layout = QHBoxLayout()
    win.btn_auto_seg_image = QPushButton("自動分割")
    seg_layout.addWidget(win.btn_auto_seg_image)
    seg_box.setLayout(seg_layout)
    right_panel.addWidget(seg_box)
    right_panel.addStretch(1)
    
    right_panel_widget = QWidget()
    right_panel_widget.setLayout(right_panel)

    win.dock_controls = QDockWidget("控制面板", win)
    win.dock_controls.setObjectName("dock_controls")
    win.dock_controls.setWidget(right_panel_widget)
    win.dock_controls.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
    win.addDockWidget(Qt.RightDockWidgetArea, win.dock_controls)

    # 版面配置
    root = QHBoxLayout()
    root.addWidget(win.video_widget)
    central.setLayout(root)

    # 在建立完各元件後加入 ToolTip
    win.btn_start_cam.setToolTip("啟動相機並顯示預覽")
    win.btn_stop_cam.setToolTip("停止相機")
    win.btn_capture.setToolTip("立即拍一張快照 Space")
    win.burst_count.setToolTip("要連續拍攝的張數")
    win.burst_interval.setToolTip("每張之間的間隔 毫秒")
    win.btn_start_burst.setToolTip("開始連拍")
    win.btn_stop_burst.setToolTip("停止連拍")
    win.btn_rec_resume.setToolTip("開始或繼續錄影 R")
    win.btn_rec_pause.setToolTip("暫停錄影")
    win.btn_rec_stop.setToolTip("停止並儲存錄影 Shift+R")
    win.btn_auto_seg_image.setToolTip("對影像執行自動分割")

    # 輕微調整版面間距
    right_panel.setSpacing(8)
    root = win.centralWidget().layout()
    root.setSpacing(12)

    # ToolTips
    win.dir_edit.setToolTip("輸出影像與影片的儲存路徑")
    win.btn_browse.setToolTip("選擇輸出資料夾")
    win.cam_combo.setToolTip("選擇要使用的相機裝置")
    win.btn_refresh_cam.setToolTip("重新掃描相機裝置")
    win.btn_start_cam.setToolTip("啟動相機預覽")
    win.btn_stop_cam.setToolTip("停止相機預覽")
    win.btn_capture.setToolTip("拍一張快照 Space")
    win.burst_count.setToolTip("連拍張數")
    win.burst_interval.setToolTip("每張間隔 毫秒")
    win.btn_start_burst.setToolTip("開始連拍")
    win.btn_stop_burst.setToolTip("停止連拍")
    win.btn_rec_resume.setToolTip("開始或繼續錄影 R")
    win.btn_rec_pause.setToolTip("暫停錄影")
    win.btn_rec_stop.setToolTip("停止錄影 Shift+R")
    win.chk_preload_sam.setToolTip("預先載入 SAM 權重以加速第一次分割")
    win.btn_auto_seg_image.setToolTip(
        "自動分割：可選單一影像或整個資料夾；已建立 embedding 的影像將略過重新分割"
    )

    # 微調間距
    right_panel.setSpacing(8)
    root = win.centralWidget().layout()
    root.setSpacing(12)


def wire_ui(win, actions):
    """把 UI 事件連到 actions（主程式不放邏輯）"""
    win.btn_browse.clicked.connect(actions.choose_dir)
    win.btn_refresh_cam.clicked.connect(actions.populate_camera_devices)
    win.btn_start_cam.clicked.connect(actions.start_camera)
    win.btn_stop_cam.clicked.connect(actions.stop_camera)
    win.btn_capture.clicked.connect(actions.capture_image)
    win.btn_start_burst.clicked.connect(actions.start_burst)
    win.btn_stop_burst.clicked.connect(actions.stop_burst)
    win.btn_rec_resume.clicked.connect(actions.resume_recording)
    win.btn_rec_pause.clicked.connect(actions.pause_recording)
    win.btn_rec_stop.clicked.connect(actions.stop_recording)
    win.btn_auto_seg_image.clicked.connect(actions.open_auto_segment_menu)

    win.chk_preload_sam.toggled.connect(actions.toggle_preload_sam)
