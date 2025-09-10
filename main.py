# webcam_snapper.py
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from modules.burst import BurstCallbacks, BurstShooter
from modules.camera_manager import CameraManager
from modules.explorer_controller import ExplorerController

# 本專案的功能模組
from modules.photo import PhotoCapture
from modules.recorder import VideoRecorder
from utils.utils import ensure_dir


# ----------------------
# 主視窗
# ----------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Webcam Snapper - Modular Edition")
        self.resize(1100, 720)

        # 模組化控制器
        self.photo_ctrl: Optional[PhotoCapture] = None
        self.burst_ctrl: Optional[BurstShooter] = None
        self.rec_ctrl: Optional[VideoRecorder] = None
        self.cam = CameraManager(self)

        # UI
        self._build_ui()

        # 初始狀態
        self._update_ui_state()
        if hasattr(self, "explorer_ctrl"):
            self.explorer_ctrl.refresh()

        # 載入相機清單（新增）
        self._populate_camera_devices()

    # ----------------------
    # UI 組裝
    # ----------------------
    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)

        # 影像預覽(VideoWidget)
        self.video_widget = QVideoWidget(self)
        self.video_widget.setMinimumSize(QSize(640, 360))

        # 儲存路徑
        dir_box = QGroupBox("輸出路徑")
        self.dir_edit = QLineEdit(str((Path.home() / "Pictures").expanduser()))
        self.btn_browse = QPushButton("瀏覽")
        self.btn_browse.clicked.connect(self._choose_dir)
        self.btn_toggle_explorer = QPushButton("檔案瀏覽")
        self.btn_toggle_explorer.setCheckable(True)
        self.btn_toggle_explorer.setChecked(True)

        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("資料夾:"))
        dir_layout.addWidget(self.dir_edit, 1)
        dir_layout.addWidget(self.btn_browse)
        dir_layout.addWidget(self.btn_toggle_explorer)
        dir_box.setLayout(dir_layout)

        # 相機設備選擇
        cam_sel_box = QGroupBox("相機設備")
        self.cam_combo = QComboBox()
        self.btn_refresh_cam = QPushButton("刷新設備")
        cam_sel_layout = QHBoxLayout()
        cam_sel_layout.addWidget(QLabel("裝置:"))
        cam_sel_layout.addWidget(self.cam_combo, 1)
        cam_sel_layout.addWidget(self.btn_refresh_cam)
        cam_sel_box.setLayout(cam_sel_layout)

        # 相機控制
        cam_box = QGroupBox("相機")
        self.btn_start_cam = QPushButton("啟動相機")
        self.btn_stop_cam = QPushButton("停止相機")
        self.btn_start_cam.clicked.connect(self.start_camera)
        self.btn_stop_cam.clicked.connect(self.stop_camera)
        cam_layout = QHBoxLayout()
        cam_layout.addWidget(self.btn_start_cam)
        cam_layout.addWidget(self.btn_stop_cam)
        cam_box.setLayout(cam_layout)

        # 拍照控制
        photo_box = QGroupBox("一般拍照")
        self.btn_capture = QPushButton("拍一張")
        self.btn_capture.clicked.connect(self.capture_image)
        photo_layout = QHBoxLayout()
        photo_layout.addWidget(self.btn_capture)
        photo_box.setLayout(photo_layout)

        # 連拍控制
        burst_box = QGroupBox("連拍")
        self.burst_count = QSpinBox()
        self.burst_count.setRange(1, 999)
        self.burst_count.setValue(5)
        self.burst_interval = QSpinBox()
        self.burst_interval.setRange(50, 10_000)
        self.burst_interval.setSingleStep(50)
        self.burst_interval.setValue(500)
        self.btn_start_burst = QPushButton("開始連拍")
        self.btn_stop_burst = QPushButton("停止連拍")
        self.btn_start_burst.clicked.connect(self.start_burst)
        self.btn_stop_burst.clicked.connect(self.stop_burst)
        burst_form = QFormLayout()
        burst_form.addRow("張數:", self.burst_count)
        burst_form.addRow("間隔(ms):", self.burst_interval)
        burst_btns = QHBoxLayout()
        burst_btns.addWidget(self.btn_start_burst)
        burst_btns.addWidget(self.btn_stop_burst)
        burst_layout = QVBoxLayout()
        burst_layout.addLayout(burst_form)
        burst_layout.addLayout(burst_btns)
        burst_box.setLayout(burst_layout)

        # 錄影控制
        rec_box = QGroupBox("錄影")
        self.btn_rec_resume = QPushButton("開始/繼續")
        self.btn_rec_pause = QPushButton("暫停")
        self.btn_rec_stop = QPushButton("停止")
        self.btn_rec_resume.clicked.connect(self.resume_recording)
        self.btn_rec_pause.clicked.connect(self.pause_recording)
        self.btn_rec_stop.clicked.connect(self.stop_recording)
        rec_layout = QHBoxLayout()
        rec_layout.addWidget(self.btn_rec_resume)
        rec_layout.addWidget(self.btn_rec_pause)
        rec_layout.addWidget(self.btn_rec_stop)
        rec_box.setLayout(rec_layout)

        # 狀態顯示
        self.status_label = QLabel("狀態: 待機")

        # 右側控制面板
        right_panel = QVBoxLayout()
        right_panel.addWidget(dir_box)
        right_panel.addWidget(cam_sel_box)
        right_panel.addWidget(cam_box)
        right_panel.addWidget(photo_box)
        right_panel.addWidget(burst_box)
        right_panel.addWidget(rec_box)
        right_panel.addStretch(1)
        right_panel.addWidget(self.status_label)

        # 版面配置
        root = QHBoxLayout()
        root.addWidget(self.video_widget, 2)
        root.addLayout(right_panel, 1)

        central.setLayout(root)

        # 建立左側可收放檔案瀏覽（改用控制器）
        self.explorer_ctrl = ExplorerController(
            self,
            self.btn_toggle_explorer,
            self.dir_edit,
        )
        self.btn_refresh_cam.clicked.connect(self._populate_camera_devices)

    # ----------------------
    # 檔案與路徑
    # ----------------------

    def _choose_dir(self):
        start_dir = Path(self.dir_edit.text()).expanduser()
        dlg = QFileDialog(self, "選擇儲存資料夾", str(start_dir))
        dlg.setFileMode(QFileDialog.Directory)
        dlg.setOption(QFileDialog.ShowDirsOnly, True)
        if dlg.exec():
            selected = dlg.selectedFiles()
            if selected:
                self.dir_edit.setText(selected[0])
            if hasattr(self, "explorer_ctrl"):
                self.explorer_ctrl.set_root_dir_from_edit()

    def _save_dir(self) -> Path:
        path = Path(self.dir_edit.text()).expanduser()
        return ensure_dir(path)

    # 相機設備管理（新增）
    def _populate_camera_devices(self):
        devices = self.cam.list_devices()
        self.cam_combo.blockSignals(True)
        self.cam_combo.clear()
        for i, (name, _dev) in enumerate(devices):
            self.cam_combo.addItem(name, i)
        self.cam_combo.blockSignals(False)
        self.btn_start_cam.setEnabled(len(devices) > 0)

    # ----------------------
    # 相機生命週期
    # ----------------------

    def start_camera(self):
        if self.cam.is_active():
            return

        # 設定選定裝置
        self.cam.set_selected_device_index(self.cam_combo.currentIndex())

        # 回呼：影像儲存、錯誤、錄影狀態、錄影錯誤
        def _on_saved(id_: int, file_path: str):
            from pathlib import Path as _P

            self.status_label.setText(f"狀態: 已儲存 {_P(file_path).name}")
            self._update_ui_state()
            self.explorer_ctrl.refresh()

        def _on_img_err(id_: int, err: int, msg: str):
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(self, "擷取影像錯誤", msg)

        def _on_rec_state(_state: int):
            self._update_ui_state()

        def _on_rec_err(_err: int, msg: str):
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(self, "錄影錯誤", msg)

        # 啟動相機（由控制器建立 session 與子控制器）
        self.cam.start(
            self.video_widget,
            on_image_saved=_on_saved,
            on_image_error=_on_img_err,
            on_rec_state_changed=_on_rec_state,
            on_rec_error=_on_rec_err,
        )

        # 取得封裝後的三個控制器供既有邏輯使用
        self.photo_ctrl = self.cam.photo
        self.burst_ctrl = self.cam.burst
        self.rec_ctrl = self.cam.rec

        self.status_label.setText("狀態: 相機啟動")
        self._update_ui_state()

    def stop_camera(self):
        self.stop_burst()
        self.cam.stop()
        self.photo_ctrl = self.burst_ctrl = self.rec_ctrl = None
        self.status_label.setText("狀態: 相機停止")
        self._update_ui_state()

    def _is_camera_active(self) -> bool:
        return self.cam.is_active()

    # ----------------------
    # 拍照
    # ----------------------
    def capture_image(self):
        if not self._is_camera_active() or self.photo_ctrl is None:
            QMessageBox.warning(self, "相機未啟動", "請先啟動相機再拍照。")
            return
        save_dir = self._save_dir()

        # 透過回呼更新狀態
        def on_saved(p: Path):
            self.status_label.setText(f"狀態: 已拍攝 {p.name}")

        try:
            self.photo_ctrl.capture_single(save_dir, on_saved=on_saved)
        except Exception as e:
            QMessageBox.critical(self, "拍照錯誤", str(e))
        finally:
            self._update_ui_state()

    # ----------------------
    # 連拍
    # ----------------------
    def start_burst(self):
        if not self._is_camera_active() or self.burst_ctrl is None:
            QMessageBox.warning(self, "相機未啟動", "請先啟動相機再開始連拍。")
            return
        count = int(self.burst_count.value())
        interval_ms = int(self.burst_interval.value())
        save_dir = self._save_dir()

        def on_progress(remaining: int):
            self.status_label.setText(f"狀態: 連拍中, 剩餘 {remaining} 張")
            self._update_ui_state()

        def on_done():
            self.status_label.setText("狀態: 連拍完成")
            self._update_ui_state()

        try:
            self.burst_ctrl.start(
                count=count,
                interval_ms=interval_ms,
                save_dir=save_dir,
                callbacks=BurstCallbacks(on_progress=on_progress, on_done=on_done),
            )
            self.status_label.setText(f"狀態: 連拍啟動, 共 {count} 張")
        except Exception as e:
            QMessageBox.critical(self, "連拍錯誤", str(e))
        finally:
            self._update_ui_state()

    def stop_burst(self):
        if self.burst_ctrl is not None and self.burst_ctrl.is_active():
            try:
                self.burst_ctrl.stop()
                self.status_label.setText("狀態: 連拍停止")
            except Exception as e:
                QMessageBox.critical(self, "停止連拍錯誤", str(e))
            finally:
                self._update_ui_state()

    # ----------------------
    # 錄影
    # ----------------------
    def resume_recording(self):
        if not self._is_camera_active() or self.rec_ctrl is None:
            QMessageBox.warning(self, "相機未啟動", "請先啟動相機再錄影。")
            return
        # 避免與連拍同時進行
        self.stop_burst()
        save_dir = self._save_dir()
        try:
            self.rec_ctrl.start_or_resume(save_dir)
            self.status_label.setText("狀態: 錄影中")
        except Exception as e:
            QMessageBox.critical(self, "錄影錯誤", str(e))
        finally:
            self._update_ui_state()

    def pause_recording(self):
        if self.rec_ctrl is None:
            return
        try:
            self.rec_ctrl.pause()
            self.status_label.setText("狀態: 錄影暫停")
        except Exception as e:
            QMessageBox.critical(self, "暫停錄影錯誤", str(e))
        finally:
            self._update_ui_state()

    def stop_recording(self):
        if self.rec_ctrl is None:
            return
        try:
            self.rec_ctrl.stop()
            self.status_label.setText("狀態: 錄影停止")
            if hasattr(self, "explorer_ctrl"):
                self.explorer_ctrl.refresh()
        except Exception as e:
            QMessageBox.critical(self, "停止錄影錯誤", str(e))
        finally:
            self._update_ui_state()

    # ----------------------
    # UI 狀態
    # ----------------------
    def _update_ui_state(self):
        cam_active = self._is_camera_active()
        in_burst = self.burst_ctrl.is_active() if self.burst_ctrl else False

        self.btn_start_cam.setEnabled(not cam_active)
        self.btn_stop_cam.setEnabled(cam_active)

        self.btn_capture.setEnabled(cam_active and not in_burst)

        self.btn_start_burst.setEnabled(cam_active and not in_burst)
        self.btn_stop_burst.setEnabled(cam_active and in_burst)
        self.burst_count.setEnabled(cam_active and not in_burst)
        self.burst_interval.setEnabled(cam_active and not in_burst)

        # 錄影按鈕狀態: 允許與拍照互斥但不與相機互斥
        self.btn_rec_resume.setEnabled(cam_active)
        self.btn_rec_pause.setEnabled(cam_active)
        self.btn_rec_stop.setEnabled(cam_active)


# ----------------------
# 程式進入點
# ----------------------
def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
