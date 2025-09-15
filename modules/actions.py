# modules/actions.py
from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDockWidget, QFileDialog, QMenu, QMessageBox, QProgressDialog

from modules.segmentation_viewer import SegmentationViewer
from modules.ui_state import update_ui_state

# 動態載入 sam_engine（不綁定固定 API 名稱）
try:
    import modules.sam_engine as sam_engine_mod
except Exception:
    sam_engine_mod = None

try:
    from modules.dock_titlebar import apply_unified_dock_titlebar
except Exception:
    apply_unified_dock_titlebar = None


# ---------------- 小工具 ----------------
def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _resolve_callable(obj: object, names: List[str]) -> Optional[Callable]:
    if obj is None:
        return None
    for name in names:
        fn = getattr(obj, name, None)
        if callable(fn):
            return fn
    return None


class Actions:
    """主視窗所有槽函式 / 操作邏輯"""

    def __init__(self, win, cam, explorer_ctrl, sam_engine_instance: Optional[object] = None):
        self.w = win
        self.cam = cam
        self.explorer = explorer_ctrl
        self.sam = sam_engine_instance  # 可為 None 或 SamEngine 實例
        self._last_ckpt: Optional[Path] = None

    # -------------- 檔案/目錄 --------------

    def choose_dir(self):
        d = QFileDialog.getExistingDirectory(self.w, "選擇輸出資料夾", str(self.w.dir_edit.text()))
        if d:
            self.w.dir_edit.setText(d)

    # -------------- 相機控制 --------------

    def populate_camera_devices(self):
        """把各種 list_devices() 回傳格式轉成 QComboBox 可接受的 (text, userData)。"""
        try:
            self.w.cam_combo.clear()
            try:
                devices = list(self.cam.list_devices())
            except Exception:
                devices = []
            for item in devices:
                text = None
                userData = None
                if isinstance(item, (tuple, list)):
                    str_elems = [x for x in item if isinstance(x, str)]
                    int_elems = [x for x in item if isinstance(x, int)]
                    if str_elems:
                        text = str_elems[0]
                        userData = int_elems[0] if int_elems else tuple(item)
                    else:
                        text = " / ".join(str(x) for x in item)
                        userData = tuple(item)
                elif isinstance(item, dict):
                    text = str(
                        item.get("name")
                        or item.get("label")
                        or item.get("path")
                        or item.get("id")
                        or "device"
                    )
                    userData = item.get("id", item.get("index", item))
                else:
                    text = str(item)
                    userData = item
                self.w.cam_combo.addItem(text, userData)
            if self.w.cam_combo.count() > 0:
                self.w.cam_combo.setCurrentIndex(0)
        except Exception as e:
            QMessageBox.critical(self.w, "讀取裝置失敗", str(e))

    def start_camera(self):
        try:
            data = self.w.cam_combo.currentData()
            idx = data if isinstance(data, int) else self.w.cam_combo.currentIndex()
            # 正確做法：先設定裝置，再只帶 widget 啟動
            try:
                self.cam.set_selected_device_index(idx)
            except Exception:
                pass
            self.cam.start(self.w.video_widget)
            self.w.status_label.setText("狀態: 相機啟動")
            update_ui_state(self.w)
        except Exception as e:
            QMessageBox.critical(self.w, "相機啟動失敗", str(e))

    def stop_camera(self):
        try:
            self.cam.stop()
            self.w.status_label.setText("狀態: 相機停止")
            update_ui_state(self.w)
        except Exception as e:
            QMessageBox.critical(self.w, "相機停止失敗", str(e))

    def capture_image(self):
        out_dir = Path(self.w.dir_edit.text())
        _ensure_dir(out_dir)
        # 直接使用 photo 控制器
        if getattr(self.cam, "photo", None) is None:
            QMessageBox.warning(self.w, "無法拍照", "相機尚未啟動或不支援拍照")
            return
        from utils.utils import build_snapshot_path

        path = build_snapshot_path(out_dir)
        # 寫入並顯示
        try:
            self.cam.photo._capture_with_retry(path)  # 與現有 PhotoCapture 保持一致
            if hasattr(self.explorer, "refresh"):
                self.explorer.refresh()
            self.w.status_label.setText(f"狀態: 已拍照 -> {Path(path).name}")
        except Exception as e:
            QMessageBox.critical(self.w, "拍照失敗", str(e))

    # -------------- 連拍 --------------

    def start_burst(self):
        if getattr(self.cam, "burst", None) is None:
            QMessageBox.warning(self.w, "無法連拍", "相機尚未啟動或不支援連拍")
            return
        out_dir = Path(self.w.dir_edit.text())
        _ensure_dir(out_dir)
        count = int(self.w.burst_count.value())
        interval = int(self.w.burst_interval.value())
        self.cam.burst.start(count, interval, out_dir)
        if hasattr(self.explorer, "refresh"):
            self.explorer.refresh()

    def stop_burst(self):
        if getattr(self.cam, "burst", None):
            self.cam.burst.stop()

    # -------------- 錄影 --------------

    def resume_recording(self):
        out_dir = Path(self.w.dir_edit.text())
        _ensure_dir(out_dir)
        if getattr(self.cam, "rec", None) is None:
            QMessageBox.warning(self.w, "無法錄影", "相機尚未啟動或不支援錄影")
            return
        self.cam.rec.start_or_resume(out_dir)
        self.w.rec_ctrl = self.cam.rec
        self.w.status_label.setText("狀態: 錄影中")

    def pause_recording(self):
        if getattr(self.w, "rec_ctrl", None) is None:
            return
        try:
            self.w.rec_ctrl.pause()
            self.w.status_label.setText("狀態: 錄影暫停")
        except Exception as e:
            QMessageBox.critical(self.w, "暫停錄影錯誤", str(e))

    def stop_recording(self):
        if getattr(self.w, "rec_ctrl", None) is None:
            return
        try:
            self.w.rec_ctrl.stop()
            self.w.status_label.setText("狀態: 錄影停止")
            if hasattr(self.explorer, "refresh"):
                self.explorer.refresh()
        except Exception as e:
            QMessageBox.critical(self.w, "停止錄影錯誤", str(e))

    # -------------- SAM 載入 --------------

    def _ensure_sam_loaded_interactive(self) -> bool:
        """若 self.sam 未就緒，互動式要求 ckpt 並載入。"""
        # 已有實例且可用
        if _resolve_callable(self.sam, ["auto_masks_from_image"]):
            return True

        if sam_engine_mod is None or not hasattr(sam_engine_mod, "SamEngine"):
            QMessageBox.warning(
                self.w, "無法載入", "找不到 SamEngine 類別，請確認 modules/sam_engine.py"
            )
            return False

        # 先用上次的 ckpt；沒有再開對話框
        ckpt: Optional[Path] = self._last_ckpt
        if ckpt is None or not Path(ckpt).exists():
            f, _ = QFileDialog.getOpenFileName(
                self.w, "選擇 SAM 權重檔 .pth", str(Path.home()), "SAM Checkpoint (*.pth *.pt)"
            )
            if not f:
                return False
            ckpt = Path(f)

        try:
            model_type = "vit_h"  # 你可改由 UI 提供選擇
            self.sam = sam_engine_mod.SamEngine(Path(ckpt), model_type=model_type)
            prog = QProgressDialog("載入 SAM 模型中...", "取消", 0, 0, self.w)
            prog.setWindowTitle("載入中")
            prog.setModal(True)
            prog.show()
            self.sam.load()
            prog.close()
            self._last_ckpt = Path(ckpt)
            self.w.status_label.setText("狀態: 模型已載入")
            return True
        except Exception as e:
            QMessageBox.critical(self.w, "載入失敗", str(e))
            self.sam = None
            return False

    def toggle_preload_sam(self, checked: bool):
        """勾選→載入模型；取消→釋放模型"""
        if checked:
            ok = self._ensure_sam_loaded_interactive()
            if not ok:
                self.w.chk_preload_sam.blockSignals(True)
                self.w.chk_preload_sam.setChecked(False)
                self.w.chk_preload_sam.blockSignals(False)
        else:
            try:
                if self.sam and _resolve_callable(self.sam, ["unload"]):
                    self.sam.unload()
                self.w.status_label.setText("狀態: 模型已卸載")
            except Exception as e:
                QMessageBox.warning(self.w, "卸載警告", str(e))

    # -------------- 自動分割：彈出選單入口 --------------

    def open_auto_segment_menu(self):
        btn = getattr(self.w, "btn_auto_seg_image", None)
        menu = QMenu(self.w)

        act_single = QAction("自動分割：選擇單一影像...", self.w)
        act_folder = QAction("自動分割：瀏覽資料夾...", self.w)
        act_last = QAction("自動分割：使用上次拍攝影像", self.w)
        act_video = QAction("自動分割：選擇影片（取第一幀）...", self.w)

        act_single.triggered.connect(self.open_segmentation_view_for_chosen_image)
        act_folder.triggered.connect(self.open_segmentation_view_for_folder_prompt)
        act_last.triggered.connect(self.open_segmentation_view_for_last_photo)
        act_video.triggered.connect(self.open_segmentation_view_for_video_file)

        menu.addAction(act_single)
        menu.addAction(act_folder)
        menu.addAction(act_last)
        menu.addSeparator()
        menu.addAction(act_video)

        if btn is not None:
            pos: QPoint = btn.mapToGlobal(btn.rect().bottomLeft())
            menu.exec(pos)
        else:
            menu.exec(self.w.mapToGlobal(self.w.rect().center()))

    # -------------- 自動分割：Helper --------------

    def _collect_images_from_dir(self, pivot: Path) -> List[Path]:
        exts = {".png", ".jpg", ".jpeg", ".bmp"}
        return [p for p in sorted(pivot.parent.glob("*")) if p.suffix.lower() in exts]

    def _ensure_sam_available(self, interactive: bool = True) -> bool:
        """若還沒載入，interactive=True 會彈窗讓使用者選 ckpt 並載入。"""
        if _resolve_callable(self.sam, ["auto_masks_from_image"]):
            return True
        if interactive:
            return self._ensure_sam_loaded_interactive()
        else:
            QMessageBox.information(
                self.w, "模型未載入", "請先在主視窗勾選『預先載入 SAM 模型』再使用自動分割。"
            )
            return False

    def _make_compute_fn_for_image(self):
        if not self._ensure_sam_available(interactive=True):
            raise RuntimeError("已取消載入 SAM 模型")
        fn = getattr(self.sam, "auto_masks_from_image", None)
        if not callable(fn):
            raise RuntimeError("目前的 SamEngine 不支援 auto_masks_from_image")
        return lambda img_path, points_per_side, pred_iou_thresh: fn(
            img_path, points_per_side=points_per_side, pred_iou_thresh=pred_iou_thresh
        )

    def _make_compute_fn_for_video_first_frame(self, video_path: Path):
        if not self._ensure_sam_available(interactive=True):
            raise RuntimeError("已取消載入 SAM 模型")
        fn = getattr(self.sam, "auto_masks_from_video_first_frame", None)
        if not callable(fn):
            raise RuntimeError("目前的 SamEngine 不支援 auto_masks_from_video_first_frame")
        return lambda _img_path, points_per_side, pred_iou_thresh: fn(
            video_path, points_per_side=points_per_side, pred_iou_thresh=pred_iou_thresh
        )

    # -------------- 自動分割：分支 --------------

    def open_segmentation_view_for_chosen_image(self):
        if not self._ensure_sam_available(interactive=True):
            return
        f, _ = QFileDialog.getOpenFileName(
            self.w, "選擇影像", str(self.w.dir_edit.text()), "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not f:
            return
        path = Path(f)
        imgs = self._collect_images_from_dir(path) or [path]
        compute_masks_fn = self._make_compute_fn_for_image()
        self._open_view(imgs, compute_masks_fn, title="自動分割檢視（單一影像/同資料夾瀏覽）")

    def open_segmentation_view_for_folder_prompt(self):
        if not self._ensure_sam_available(interactive=True):
            return
        d = QFileDialog.getExistingDirectory(self.w, "選擇資料夾", str(self.w.dir_edit.text()))
        if not d:
            return
        folder = Path(d)
        exts = {".png", ".jpg", ".jpeg", ".bmp"}
        imgs = [p for p in sorted(folder.glob("*")) if p.suffix.lower() in exts]
        if not imgs:
            QMessageBox.information(self.w, "沒有影像", "該資料夾內沒有支援格式的影像檔。")
            return
        compute_masks_fn = self._make_compute_fn_for_image()
        self._open_view(imgs, compute_masks_fn, title=f"自動分割檢視（{folder.name}）")

    def open_segmentation_view_for_last_photo(self):
        if not self._ensure_sam_available(interactive=True):
            return
        last = None
        if hasattr(self.explorer, "last_image_path"):
            last = self.explorer.last_image_path()
        if last is None or not Path(last).exists():
            f, _ = QFileDialog.getOpenFileName(
                self.w, "選擇影像", str(self.w.dir_edit.text()), "Images (*.png *.jpg *.jpeg *.bmp)"
            )
            if not f:
                return
            last = Path(f)
        else:
            last = Path(last)
        imgs = self._collect_images_from_dir(last) or [last]
        compute_masks_fn = self._make_compute_fn_for_image()
        self._open_view(imgs, compute_masks_fn, title="自動分割檢視（上次拍攝影像）")

    def open_segmentation_view_for_video_file(self):
        if not self._ensure_sam_available(interactive=True):
            return
        f, _ = QFileDialog.getOpenFileName(
            self.w, "選擇影片", str(self.w.dir_edit.text()), "Videos (*.mp4 *.mov *.avi *.mkv)"
        )
        if not f:
            return
        video_path = Path(f)
        compute_masks_fn = self._make_compute_fn_for_video_first_frame(video_path)
        self._open_view(
            [video_path], compute_masks_fn, title=f"影片第一幀分割檢視（{video_path.name}）"
        )

    def open_segmentation_view_for_last_video(self):
        if not self._ensure_sam_available(interactive=True):
            return
        if hasattr(self.explorer, "last_video_path"):
            vp = self.explorer.last_video_path()
        else:
            vp = None
        if vp is None or not Path(vp).exists():
            return self.open_segmentation_view_for_video_file()
        compute_masks_fn = self._make_compute_fn_for_video_first_frame(Path(vp))
        self._open_view(
            [Path(vp)], compute_masks_fn, title=f"影片第一幀分割檢視（{Path(vp).name}）"
        )

    # -------------- 開啟分割檢視（共用） --------------

    def _open_view(self, image_paths, compute_masks_fn, title: str):
        # 保留視窗引用，避免被 GC
        if not hasattr(self, "_seg_windows"):
            self._seg_windows = []

        viewer = SegmentationViewer(
            self.w,  # 原本是 None，改成主視窗作為父層
            image_paths,
            compute_masks_fn,
            params_defaults={
                "points_per_side": 32,
                "pred_iou_thresh": 0.88,
            },
            title=title,
        )
        viewer.setAttribute(Qt.WA_DeleteOnClose, True)

        # 視窗關閉時，移除引用
        def _drop_ref(*_):
            if viewer in self._seg_windows:
                self._seg_windows.remove(viewer)

        try:
            viewer.destroyed.connect(_drop_ref)
        except Exception:
            pass

        self._seg_windows.append(viewer)
        viewer.show()
        viewer.raise_()
        viewer.activateWindow()
