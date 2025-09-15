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
)


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
    win.btn_toggle_explorer = QPushButton("檔案瀏覽")
    win.btn_toggle_explorer.setCheckable(True)
    win.btn_toggle_explorer.setChecked(True)
    dir_layout = QHBoxLayout()
    dir_layout.addWidget(QLabel("資料夾:"))
    dir_layout.addWidget(win.dir_edit, 1)
    dir_layout.addWidget(win.btn_browse)
    dir_layout.addWidget(win.btn_toggle_explorer)
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

    # 狀態列
    win.status_label = QLabel("狀態: 待機")

    # 右側
    right_panel = QVBoxLayout()
    right_panel.addWidget(dir_box)
    right_panel.addWidget(cam_sel_box)
    right_panel.addWidget(cam_box)
    right_panel.addWidget(photo_box)
    right_panel.addWidget(burst_box)
    right_panel.addWidget(rec_box)
    win.chk_preload_sam = QCheckBox("預先載入 SAM 模型")
    right_panel.addWidget(win.chk_preload_sam)  # 建議放在分割工具 group 上方
    seg_box = QGroupBox("分割工具")
    seg_layout = QHBoxLayout()
    win.btn_auto_seg_image = QPushButton("自動分割影像")
    win.btn_auto_seg_video = QPushButton("自動分割影片")
    seg_layout.addWidget(win.btn_auto_seg_image)
    seg_layout.addWidget(win.btn_auto_seg_video)
    seg_box.setLayout(seg_layout)
    right_panel.addWidget(seg_box)
    right_panel.addStretch(1)
    right_panel.addWidget(win.status_label)

    # 版面配置
    root = QHBoxLayout()
    root.addWidget(win.video_widget, 2)
    root.addLayout(right_panel, 1)
    central.setLayout(root)


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
    win.btn_auto_seg_video.clicked.connect(actions.open_segmentation_view_for_last_video)
    win.chk_preload_sam.toggled.connect(actions.toggle_preload_sam)
