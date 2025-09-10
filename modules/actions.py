# modules/actions.py
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from modules.burst import BurstCallbacks
from modules.ui_state import update_ui_state
from utils.utils import ensure_dir


class Actions:
    """把所有槽函式/操作邏輯集中於此"""

    def __init__(self, win, cam, explorer_ctrl):
        self.w = win  # MainWindow
        self.cam = cam  # CameraManager
        self.explorer = explorer_ctrl  # ExplorerController

    # -------- 輔助 --------
    def _save_dir(self) -> Path:
        return ensure_dir(Path(self.w.dir_edit.text()).expanduser())

    # -------- UI 操作 --------
    def populate_camera_devices(self):
        devices = self.cam.list_devices()
        self.w.cam_combo.blockSignals(True)
        self.w.cam_combo.clear()
        for i, (name, _dev) in enumerate(devices):
            self.w.cam_combo.addItem(name, i)
        self.w.cam_combo.blockSignals(False)
        self.w.btn_start_cam.setEnabled(len(devices) > 0)

    def choose_dir(self):
        start_dir = Path(self.w.dir_edit.text()).expanduser()
        dlg = QFileDialog(self.w, "選擇儲存資料夾", str(start_dir))
        dlg.setFileMode(QFileDialog.Directory)
        dlg.setOption(QFileDialog.ShowDirsOnly, True)
        if dlg.exec():
            selected = dlg.selectedFiles()
            if selected:
                self.w.dir_edit.setText(selected[0])
                self.explorer.set_root_dir_from_edit()

    # -------- 相機生命週期 --------
    def start_camera(self):
        if self.cam.is_active():
            return
        self.cam.set_selected_device_index(self.w.cam_combo.currentIndex())

        def _on_saved(id_: int, file_path: str):
            from pathlib import Path as _P

            self.w.status_label.setText(f"狀態: 已儲存 {_P(file_path).name}")
            update_ui_state(self.w)
            self.explorer.refresh()

        def _on_img_err(id_: int, err: int, msg: str):
            QMessageBox.critical(self.w, "擷取影像錯誤", msg)

        def _on_rec_state(_state: int):
            update_ui_state(self.w)

        def _on_rec_err(_err: int, msg: str):
            QMessageBox.critical(self.w, "錄影錯誤", msg)

        self.cam.start(
            self.w.video_widget,
            on_image_saved=_on_saved,
            on_image_error=_on_img_err,
            on_rec_state_changed=_on_rec_state,
            on_rec_error=_on_rec_err,
        )
        # 暴露控制器給 UI 狀態查詢
        self.w.photo_ctrl = self.cam.photo
        self.w.burst_ctrl = self.cam.burst
        self.w.rec_ctrl = self.cam.rec

        self.w.status_label.setText("狀態: 相機啟動")
        update_ui_state(self.w)

    def stop_camera(self):
        self.stop_burst()
        self.cam.stop()
        self.w.photo_ctrl = self.w.burst_ctrl = self.w.rec_ctrl = None
        self.w.status_label.setText("狀態: 相機停止")
        update_ui_state(self.w)

    # -------- 拍照 / 連拍 --------
    def capture_image(self):
        if not self.cam.is_active() or self.w.photo_ctrl is None:
            QMessageBox.warning(self.w, "相機未啟動", "請先啟動相機再拍照。")
            return
        save_dir = self._save_dir()

        def on_saved(p: Path):
            self.w.status_label.setText(f"狀態: 已拍攝 {p.name}")

        try:
            self.w.photo_ctrl.capture_single(save_dir, on_saved=on_saved)
        except Exception as e:
            QMessageBox.critical(self.w, "拍照錯誤", str(e))
        finally:
            update_ui_state(self.w)

    def start_burst(self):
        if not self.cam.is_active() or self.w.burst_ctrl is None:
            QMessageBox.warning(self.w, "相機未啟動", "請先啟動相機再開始連拍。")
            return
        count = int(self.w.burst_count.value())
        interval_ms = int(self.w.burst_interval.value())
        save_dir = self._save_dir()

        def on_progress(remaining: int):
            self.w.status_label.setText(f"狀態: 連拍中, 剩餘 {remaining} 張")
            update_ui_state(self.w)

        def on_done():
            self.w.status_label.setText("狀態: 連拍完成")
            update_ui_state(self.w)

        try:
            self.w.burst_ctrl.start(
                count=count,
                interval_ms=interval_ms,
                save_dir=save_dir,
                callbacks=BurstCallbacks(on_progress=on_progress, on_done=on_done),
            )
            self.w.status_label.setText(f"狀態: 連拍啟動, 共 {count} 張")
        except Exception as e:
            QMessageBox.critical(self.w, "連拍錯誤", str(e))
        finally:
            update_ui_state(self.w)

    def stop_burst(self):
        if self.w.burst_ctrl is not None and self.w.burst_ctrl.is_active():
            try:
                self.w.burst_ctrl.stop()
                self.w.status_label.setText("狀態: 連拍停止")
            except Exception as e:
                QMessageBox.critical(self.w, "停止連拍錯誤", str(e))
            finally:
                update_ui_state(self.w)

    # -------- 錄影 --------
    def resume_recording(self):
        if not self.cam.is_active() or self.w.rec_ctrl is None:
            QMessageBox.warning(self.w, "相機未啟動", "請先啟動相機再錄影。")
            return
        self.stop_burst()
        save_dir = self._save_dir()
        try:
            self.w.rec_ctrl.start_or_resume(save_dir)
            self.w.status_label.setText("狀態: 錄影中")
        except Exception as e:
            QMessageBox.critical(self.w, "錄影錯誤", str(e))
        finally:
            update_ui_state(self.w)

    def pause_recording(self):
        if self.w.rec_ctrl is None:
            return
        try:
            self.w.rec_ctrl.pause()
            self.w.status_label.setText("狀態: 錄影暫停")
        except Exception as e:
            QMessageBox.critical(self.w, "暫停錄影錯誤", str(e))
        finally:
            update_ui_state(self.w)

    def stop_recording(self):
        if self.w.rec_ctrl is None:
            return
        try:
            self.w.rec_ctrl.stop()
            self.w.status_label.setText("狀態: 錄影停止")
            self.explorer.refresh()
        except Exception as e:
            QMessageBox.critical(self.w, "停止錄影錯誤", str(e))
        finally:
            update_ui_state(self.w)
