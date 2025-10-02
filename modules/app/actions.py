# modules/actions.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List, Optional
from urllib.request import urlretrieve

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox

from modules.presentation.qt.segmentation.segmentation_viewer import SegmentationViewer
from modules.presentation.qt.ui_state import update_ui_state

# 動態載入 sam_engine（不綁定固定 API 名稱）
try:
    import modules.infrastructure.vision.sam_engine as sam_engine_mod
except Exception:
    sam_engine_mod = None

DEFAULT_SAM_MODEL_TYPE = "vit_h"
DEFAULT_SAM_CKPT = Path("./models/sam_vit_h_4b8939.pth")
DEFAULT_SAM_URL = "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth"

logger = logging.getLogger(__name__)


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

        try:
            dock = getattr(self.explorer, "explorer", None)
            if dock is not None and hasattr(dock, "files_segment_requested"):
                dock.files_segment_requested.connect(self.open_segmentation_for_file_list)
        except Exception:
            pass
        self.default_params = {
            "points_per_side": 32,
            "pred_iou_thresh": 0.88,
            "union_morph_enabled": True,
            "union_morph_scale": 0.003,
            "fit_on_open": True,
        }

    def _on_output_dir_changed(self, path: str) -> None:
        pass

    # 供 main.py 用名稱選定裝置
    def select_camera_by_name(self, name: str) -> None:
        try:
            cb = self.w.cam_combo
            for i in range(cb.count()):
                if cb.itemText(i) == name:
                    cb.setCurrentIndex(i)
                    break
        except Exception:
            pass

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
            try:
                self.cam.set_selected_device_index(idx)
            except Exception:
                pass
            self.cam.start(self.w.video_widget)
            self.w.status.message("狀態：相機啟動")

            update_ui_state(self.w)
        except Exception as e:
            QMessageBox.critical(self.w, "相機啟動失敗", str(e))

    def stop_camera(self):
        try:
            self.cam.stop()
            self.w.status.message("狀態：相機停止")
            update_ui_state(self.w)
        except Exception as e:
            QMessageBox.critical(self.w, "相機停止失敗", str(e))

    def capture_image(self):
        out_dir = Path(self.w.dir_edit.text())
        _ensure_dir(out_dir)
        if getattr(self.cam, "photo", None) is None:
            QMessageBox.warning(self.w, "無法拍照", "相機尚未啟動或不支援拍照")
            return
        try:
            # 交由公開方法自動命名與重試
            self.cam.photo.capture_single(out_dir)
            if hasattr(self.explorer, "refresh"):
                self.explorer.refresh()
            self.w.status.message("狀態：已拍照")
        except Exception as e:
            logger.exception("拍照失敗")
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
        self.w.burst_ctrl = self.cam.burst
        update_ui_state(self.w)
        if hasattr(self.explorer, "refresh"):
            self.explorer.refresh()

    def stop_burst(self):
        if getattr(self.cam, "burst", None):
            self.cam.burst.stop()
        self.w.burst_ctrl = None
        update_ui_state(self.w)

    # -------------- 錄影 --------------

    def resume_recording(self):
        from pathlib import Path

        out_dir = Path(self.w.dir_edit.text())
        _ensure_dir(out_dir)
        if getattr(self.cam, "rec", None) is None:
            logger.warning("錄影控制器不存在或相機未啟動")
            QMessageBox.warning(self.w, "無法錄影", "相機尚未啟動或不支援錄影")
            return
        self.cam.rec.start_or_resume(out_dir)
        self.w.rec_ctrl = self.cam.rec
        self.w.status.message("狀態：錄影中")

    def pause_recording(self):
        if getattr(self.w, "rec_ctrl", None) is None:
            return
        try:
            self.w.rec_ctrl.pause()
            self.w.status.message("狀態：錄影暫停")
        except Exception as e:
            QMessageBox.critical(self.w, "暫停錄影錯誤", str(e))

    def stop_recording(self):
        if getattr(self.w, "rec_ctrl", None) is None:
            return
        try:
            self.w.rec_ctrl.stop()
            self.w.status.message("狀態：錄影停止")
            if hasattr(self.explorer, "refresh"):
                self.explorer.refresh()
        except Exception as e:
            logger.exception("停止錄影錯誤")
            QMessageBox.critical(self.w, "停止錄影錯誤", str(e))

    # -------------- SAM 載入 --------------

    # 【修改】優先使用預設路徑，否則詢問下載，同意才下載，否則回退檔案選取
    def _ensure_sam_loaded_interactive(self) -> bool:
        """若 self.sam 未就緒，優先使用預設 ckpt；無檔時詢問下載，同意後才下載並載入；最後才回退檔案選取。"""
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog, QMessageBox

        if _resolve_callable(self.sam, ["auto_masks_from_image"]):
            return True
        if sam_engine_mod is None or not hasattr(sam_engine_mod, "SamEngine"):
            QMessageBox.warning(
                self.w, "無法載入", "找不到 SamEngine 類別，請確認 modules/sam_engine.py"
            )
            return False

        ckpt: Optional[Path] = self._last_ckpt

        # 1) 嘗試使用預設路徑
        if ckpt is None or not Path(ckpt).exists():
            default = DEFAULT_SAM_CKPT
            if default.exists():
                ckpt = default
            else:
                # 2) 詢問是否下載，使用者同意就下載
                try:
                    maybe = self._download_sam_with_prompt()
                    if maybe is not None:
                        ckpt = maybe
                except Exception as e:
                    logger.exception("下載 SAM 權重失敗")
                    QMessageBox.critical(self.w, "下載 SAM 權重失敗", str(e))

        # 3) 若仍沒有 ckpt，回退到舊的檔案選取流程
        if ckpt is None or not Path(ckpt).exists():
            f, _ = QFileDialog.getOpenFileName(
                self.w, "選擇 SAM 權重檔 .pth", str(Path.home()), "SAM Checkpoint (*.pth *.pt)"
            )
            if not f:
                return False
            ckpt = Path(f)

        try:
            model_type = DEFAULT_SAM_MODEL_TYPE  # 預設使用 vit_h
            self.sam = sam_engine_mod.SamEngine(Path(ckpt), model_type=model_type)
            self.w.status.start_scifi_simulated("載入 SAM 模型中...", start=25, stop_at=99)
            self.sam.load()
            self.w.status.stop_scifi("狀態：模型已載入")
            self._last_ckpt = Path(ckpt)
            return True
        except Exception as e:
            self.w.status.stop_scifi("狀態：模型載入失敗")
            logger.exception("SAM 模型載入失敗")
            QMessageBox.critical(self.w, "載入失敗", str(e))
            self.sam = None
            return False

    def toggle_preload_sam(self, checked: bool):
        if checked:
            ok = self._ensure_sam_loaded_interactive()
            if not ok:
                self.w.chk_preload_sam.blockSignals(True)
                self.w.chk_preload_sam.setChecked(False)
                self.w.chk_preload_sam.blockSignals(False)
        else:
            try:
                if self.sam and _resolve_callable(self.sam, ["unload"]):
                    self.w.status.start_scifi("卸載 SAM 模型中...")
                    try:
                        self.sam.unload()
                    finally:
                        self.w.status.stop_scifi("狀態：模型已卸載")
                else:
                    self.w.status.message("狀態：模型已卸載")
                self.sam = None
            except Exception as e:
                # 萬一發生例外，關掉彈窗並提示
                self.w.status.stop_scifi("狀態：模型卸載失敗")
                QMessageBox.warning(self.w, "卸載警告", str(e))

    # -------------- 自動分割：彈出選單入口 --------------

    # 取代原 open_auto_segment_menu
    def open_auto_segment_menu(self):
        btn = getattr(self.w, "btn_auto_seg_image", None)
        menu = QMenu(self.w)

        act_single = QAction("自動分割：選擇單一影像...", self.w)
        act_folder = QAction("自動分割：瀏覽資料夾（批次）...", self.w)

        act_single.triggered.connect(self.open_segmentation_view_for_chosen_image)
        act_folder.triggered.connect(self.open_segmentation_view_for_folder_prompt)

        menu.addAction(act_single)
        menu.addAction(act_folder)

        if btn is not None:
            pos: QPoint = btn.mapToGlobal(btn.rect().bottomLeft())
            menu.exec(pos)
        else:
            menu.exec(self.w.mapToGlobal(self.w.rect().center()))

    # -------------- 自動分割：Helper --------------

    def _collect_images_from_dir(self, pivot: Path) -> List[Path]:
        exts = {".png", ".jpg", ".jpeg", ".bmp"}
        return [
            p for p in sorted(pivot.parent.glob("*")) if p.is_file() and p.suffix.lower() in exts
        ]

    @staticmethod
    def _safe_resolve(p: Path) -> Path:
        try:
            return p.resolve()
        except Exception:
            return p

    def _collect_images_with_pivot_first(self, pivot: Path) -> List[Path]:
        """回傳同資料夾影像清單, 並將 pivot 排到第 1 筆"""
        imgs = self._collect_images_from_dir(pivot) or []
        pv = self._safe_resolve(pivot)
        head = [p for p in imgs if self._safe_resolve(p) == pv]
        tail = [p for p in imgs if self._safe_resolve(p) != pv]
        return (head or [pivot]) + tail

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

    # 取代原 _make_compute_fn_for_image
    def _make_compute_fn_for_image(self):
        if not self._ensure_sam_available(interactive=True):
            raise RuntimeError("已取消載入 SAM 模型")
        # 優先使用快取版
        fn_cached = getattr(self.sam, "auto_masks_from_image_cached", None)
        if callable(fn_cached):
            return lambda img_path, points_per_side, pred_iou_thresh: fn_cached(
                img_path, points_per_side=points_per_side, pred_iou_thresh=pred_iou_thresh
            )
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
        imgs = self._collect_images_with_pivot_first(path)
        compute_masks_fn = self._make_compute_fn_for_image()
        self._open_view(imgs, compute_masks_fn, title=f"自動分割檢視（{path.name}）")

    def open_segmentation_view_for_folder_prompt(self):
        if not self._ensure_sam_available(interactive=True):
            return
        d = QFileDialog.getExistingDirectory(self.w, "選擇資料夾", str(self.w.dir_edit.text()))
        if not d:
            return
        folder = Path(d)
        exts = {".png", ".jpg", ".jpeg", ".bmp"}
        imgs = [p for p in sorted(folder.glob("*")) if p.is_file() and p.suffix.lower() in exts]
        if not imgs:
            QMessageBox.information(self.w, "沒有影像", "該資料夾內沒有支援格式的影像檔。")
            return
        compute_masks_fn = self._make_compute_fn_for_image()

        # 批次先建立/更新快取：已有 embedding 的影像會自動略過重算
        try:
            self.w.status.start_scifi("批次分割中：建立快取與 embedding")
            for p in imgs:
                try:
                    pps = self.default_params["points_per_side"]
                    iou = self.default_params["pred_iou_thresh"]
                    self.sam.auto_masks_from_image_cached(
                        p, points_per_side=pps, pred_iou_thresh=iou
                    )
                except Exception:
                    logger.exception("批次建立快取時發生錯誤: %s", p)
        finally:
            self.w.status.stop_scifi()

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
        imgs = self._collect_images_with_pivot_first(last)
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
        params = {
            "points_per_side": self.default_params["points_per_side"],
            "pred_iou_thresh": self.default_params["pred_iou_thresh"],
            "union_morph_enabled": self.default_params["union_morph_enabled"],
            "union_morph_scale": self.default_params["union_morph_scale"],
            "fit_on_open": self.default_params["fit_on_open"],
        }

        viewer = SegmentationViewer(
            None,  # 原本是 None，改成主視窗作為父層
            image_paths,
            compute_masks_fn,
            params_defaults=params,
            title=title,
        )
        viewer.setAttribute(Qt.WA_DeleteOnClose, True)
        viewer.setWindowFlag(Qt.Window, True)

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

    def _download_sam_with_prompt(self) -> Optional[Path]:
        dst = DEFAULT_SAM_CKPT
        if dst.exists():
            return dst

        ret = QMessageBox.question(
            self.w,
            "下載 SAM 權重",
            "找不到預設 SAM 權重檔:\nmodels/sam_vit_h_4b8939.pth\n\n要立即下載並儲存到 models/ 嗎？\n檔案約 2.5GB，時間視網路速度而定。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if ret != QMessageBox.Yes:
            return None

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            self.w.status.start_scifi("下載 SAM 權重中...")

            last_percent = -1

            def hook(blocknum, blocksize, totalsize):
                nonlocal last_percent
                if totalsize > 0:
                    percent = int(min(100, (blocknum * blocksize * 100) // totalsize))
                    if percent != last_percent:
                        last_percent = percent
                        # 顯示百分比並讓 UI 及時更新
                        self.w.status.set_scifi_progress(percent, f"下載 SAM 權重中... {percent}%")

            urlretrieve(DEFAULT_SAM_URL, str(dst), reporthook=hook)
            self.w.status.stop_scifi("狀態：SAM 權重下載完成")
            return dst
        except Exception as e:
            self.w.status.stop_scifi("狀態：SAM 權重下載失敗")
            logger.exception("下載 SAM 權重失敗")
            QMessageBox.critical(self.w, "下載失敗", str(e))
            try:
                # 下載失敗時清掉未完成檔
                if dst.exists():
                    dst.unlink()
            except Exception:
                logger.warning("清理未完成 SAM 權重暫存檔失敗", exc_info=True)
            return None

    # 新增：由 Dock 多選觸發, 選幾張就開幾個視窗
    def open_segmentation_for_file_list(self, paths: list[str]):
        if not paths:
            return
        if not self._ensure_sam_available(interactive=True):
            return
        compute_masks_fn = self._make_compute_fn_for_image()  # 一次建立
        for s in paths:
            p = Path(s)
            if not p.exists() or not p.is_file():
                continue
            imgs = self._collect_images_with_pivot_first(p)
            self._open_view(imgs, compute_masks_fn, title=f"自動分割檢視（{p.name}）")
