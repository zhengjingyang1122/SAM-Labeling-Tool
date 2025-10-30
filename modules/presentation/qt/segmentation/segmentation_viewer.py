# modules/segmentation_viewer.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import cv2
import numpy as np
from PySide6.QtCore import QDir, QEvent, QPoint, QRectF, Qt
from PySide6.QtGui import QAction, QImage, QPainter, QPixmap, QTransform
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFileSystemModel,
    QFormLayout,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from modules.presentation.qt.explorer.explorer import MediaExplorer
from modules.presentation.qt.shortcuts import get_app_shortcut_manager
from modules.presentation.qt.status_footer import StatusFooter

logger = logging.getLogger(__name__)


# ---------- helpers ----------
def np_bgr_to_qpixmap(bgr: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


def compute_bbox(mask: np.ndarray) -> Tuple[int, int, int, int]:
    ys, xs = np.where(mask > 0)
    if ys.size == 0:
        return 0, 0, mask.shape[1], mask.shape[0]
    x1, x2 = xs.min(), xs.max()
    y1, y2 = ys.min(), ys.max()
    return int(x1), int(y1), int(x2 - x1 + 1), int(y2 - y1 + 1)


# ---------- QGraphicsView-based image view ----------


class ImageView(QGraphicsView):

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pix_item: Optional[QGraphicsPixmapItem] = None
        self.setRenderHints(
            self.renderHints() | QPainter.Antialiasing | QPainter.SmoothPixmapTransform
        )
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setMouseTracking(True)

    def set_image_bgr(self, bgr: np.ndarray) -> None:
        pix = np_bgr_to_qpixmap(bgr)
        if self._pix_item is None:
            self._pix_item = self._scene.addPixmap(pix)
            self._pix_item.setZValue(0)
            self._scene.setSceneRect(QRectF(pix.rect()))
            self.reset_view()
        else:
            self._pix_item.setPixmap(pix)
            self._scene.setSceneRect(QRectF(pix.rect()))

    def wheelEvent(self, ev) -> None:
        delta = ev.angleDelta().y()
        if delta == 0:
            return
        factor = pow(1.0015, delta)  # 平滑倍率
        self.scale(factor, factor)

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            # 轉送成左鍵給 QGraphicsView 內部開始拖曳
            fake = type(ev)(
                QEvent.MouseButtonPress,
                ev.position(),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            super().mousePressEvent(fake)
            ev.accept()
        else:
            super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.MiddleButton:
            fake = type(ev)(
                QEvent.MouseButtonRelease,
                ev.position(),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
            super().mouseReleaseEvent(fake)
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            ev.accept()
        else:
            super().mouseReleaseEvent(ev)

    def reset_view(self) -> None:
        self.setTransform(QTransform())
        if self._pix_item is not None:
            self.centerOn(self._pix_item)

    def map_widget_to_image(self, p: QPoint) -> Optional[Tuple[int, int]]:
        if self._pix_item is None:
            return None
        scene_pt = self.mapToScene(p)
        img_x = int(scene_pt.x())
        img_y = int(scene_pt.y())
        rect = self._pix_item.pixmap().rect()
        if not rect.contains(img_x, img_y):
            return None
        img_x = max(0, min(img_x, rect.width() - 1))
        img_y = max(0, min(img_y, rect.height() - 1))
        return img_x, img_y


# ---------- Main viewer ----------


class SegmentationViewer(QMainWindow):
    def __init__(
        self,
        parent: Optional[QWidget],
        image_paths: List[Path],
        compute_masks_fn: Callable[
            [Path, int, float], Tuple[np.ndarray, List[np.ndarray], List[float]]
        ],
        params_defaults: Optional[Dict[str, float]] = None,
        title: str = "分割檢視",
        path_manager: Optional["PathManager"] = None,  # 注入 PathManager
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.Window, True)
        self.setWindowModality(Qt.NonModal)

        self.image_paths: List[Path] = list(image_paths)
        self.idx: int = 0
        self.compute_masks_fn = compute_masks_fn
        self.pm = path_manager  # 保存 PathManager 實例
        self.params = {
            "points_per_side": int((params_defaults or {}).get("points_per_side", 32)),
            "pred_iou_thresh": float((params_defaults or {}).get("pred_iou_thresh", 0.88)),
        }
        self.cache: Dict[Path, Tuple[np.ndarray, List[np.ndarray], List[float]]] = {}
        self.selected_indices: set[int] = set()
        self._hover_idx: Optional[int] = None

        # image view
        self.view = ImageView(self)
        self.view.viewport().installEventFilter(self)  # hover/點選 hit test

        # 右側群組 UI
        grp_nav = QGroupBox("導覽")
        self.btn_prev = QPushButton("← 上一張")
        self.btn_next = QPushButton("下一張 →")
        self.btn_reset_view = QPushButton("重設畫布")
        lay_nav = QHBoxLayout()
        lay_nav.addWidget(self.btn_prev)
        lay_nav.addWidget(self.btn_next)
        lay_nav.addWidget(self.btn_reset_view)
        grp_nav.setLayout(lay_nav)

        grp_crop = QGroupBox("輸出裁切模式")
        self.rb_full = QRadioButton("原圖大小")
        self.rb_bbox = QRadioButton("最小外接矩形")
        self.rb_bbox.setChecked(True)
        self.crop_group = QButtonGroup(self)
        self.crop_group.addButton(self.rb_full, 0)
        self.crop_group.addButton(self.rb_bbox, 1)
        lay_crop = QVBoxLayout()
        lay_crop.addWidget(self.rb_bbox)
        lay_crop.addWidget(self.rb_full)
        grp_crop.setLayout(lay_crop)

        grp_mode = QGroupBox("輸出模式")
        self.rb_mode_union = QRadioButton("疊加聯集(單檔輸出)")
        self.rb_mode_indiv = QRadioButton("個別獨立(多檔輸出)")
        self.rb_mode_indiv.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_mode_indiv, 0)
        self.mode_group.addButton(self.rb_mode_union, 1)
        lay_mode = QVBoxLayout()
        lay_mode.addWidget(self.rb_mode_indiv)
        lay_mode.addWidget(self.rb_mode_union)
        grp_mode.setLayout(lay_mode)
        # [新增] 顯示模式切換群組，放在 grp_mode 定義之後
        grp_display = QGroupBox("顯示模式")
        self.rb_show_mask = QRadioButton("遮罩高亮")
        self.rb_show_bbox = QRadioButton("Bounding Box")
        self.rb_show_mask.setChecked(True)

        self.display_group = QButtonGroup(self)
        self.display_group.addButton(self.rb_show_mask, 0)  # 0=遮罩
        self.display_group.addButton(self.rb_show_bbox, 1)  # 1=BBox

        lay_display = QVBoxLayout()
        lay_display.addWidget(self.rb_show_mask)
        lay_display.addWidget(self.rb_show_bbox)
        grp_display.setLayout(lay_display)

        # 切換顯示模式即時重繪
        self.display_group.idClicked.connect(lambda _id: self._update_canvas())

        # [新增] 輸出模式切換時也要重繪（為了 BBox 聯集時只畫一個框）
        self.mode_group.idClicked.connect(lambda _id: self._update_canvas())

        # [新增] 建立在 grp_mode 與 grp_save 之間，與其它群組同一層級
        grp_labels = QGroupBox("輸出標註格式")
        self.chk_yolo_det = QCheckBox("YOLO 檢測 bbox")
        self.chk_yolo_seg = QCheckBox("YOLO 分割 polygon")

        self.spn_cls = QSpinBox()
        self.spn_cls.setRange(0, 999)
        self.spn_cls.setValue(0)

        lay_labels = QFormLayout()
        lay_labels.addRow(self.chk_yolo_det)
        lay_labels.addRow(self.chk_yolo_seg)
        lay_labels.addRow("class_id", self.spn_cls)
        grp_labels.setLayout(lay_labels)

        grp_save = QGroupBox("儲存")
        self.btn_save_selected = QPushButton("儲存已選目標(.png)")
        self.lbl_selected = QLabel("已選目標：0")
        lay_save = QVBoxLayout()
        lay_save.addWidget(self.btn_save_selected)
        lay_save.addWidget(self.lbl_selected)
        grp_save.setLayout(lay_save)

        grp_params = QGroupBox("自動分割參數")
        form = QFormLayout()
        self.spn_points = QSpinBox()
        self.spn_points.setRange(4, 128)
        self.spn_points.setValue(self.params["points_per_side"])
        self.spn_iou = QDoubleSpinBox()
        self.spn_iou.setRange(0.1, 0.99)
        self.spn_iou.setSingleStep(0.01)
        self.spn_iou.setValue(self.params["pred_iou_thresh"])
        self.btn_apply_params = QPushButton("套用參數並重算本張")
        form.addRow("points_per_side", self.spn_points)
        form.addRow("pred_iou_thresh", self.spn_iou)
        form.addRow(self.btn_apply_params)
        grp_params.setLayout(form)

        right_box = QVBoxLayout()
        right_box.addWidget(grp_nav)
        right_box.addWidget(grp_crop)
        right_box.addWidget(grp_mode)
        right_box.addWidget(grp_display)
        right_box.addWidget(grp_labels)
        right_box.addWidget(grp_save)
        right_box.addWidget(grp_params)
        right_box.addStretch(1)
        right_widget = QWidget()
        right_widget.setLayout(right_box)

        central = QWidget(self)
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        main.addWidget(self.view, 1)
        main.addWidget(right_widget, 0)

        # 左側檔案樹 dock（與主視窗統一標題列文字按鈕）
        self._build_left_dock()



        mgr = get_app_shortcut_manager()
        mgr.register_viewer(self)

        # connect
        self.btn_reset_view.clicked.connect(self.view.reset_view)
        self.btn_apply_params.clicked.connect(self._apply_params)
        self.btn_prev.clicked.connect(self._prev_image)
        self.btn_next.clicked.connect(self._next_image)
        self.btn_save_selected.clicked.connect(self._save_selected)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.status = StatusFooter.install(self)
        self._spawned_views: list[SegmentationViewer] = []
        self.status.message("準備就緒")

        self._load_current_image(recompute=True)

    def _build_left_dock(self) -> None:
        # 與主視窗一致：使用 MediaExplorer，但不顯示「合併回主視窗」按鈕
        name_filters = [
            "*.png",
            "*.jpg",
            "*.jpeg",
            "*.bmp",
            "*.tif",
            "*.tiff",
            "*.gif",
            "*.webp",
            "*.mp4",
            "*.mov",
            "*.avi",
            "*.mkv",
        ]
        explorer = MediaExplorer(self, name_filters=name_filters)
        self.addDockWidget(Qt.LeftDockWidgetArea, explorer)

        # 設定根目錄：預設到目前影像所在資料夾（同資料夾瀏覽體驗）
        if self.image_paths:
            explorer.set_root_dir(Path(self.image_paths[0]).parent)

        # 與既有邏輯對接：沿用原本的雙擊行為
        explorer.tree.doubleClicked.connect(self._on_tree_double_clicked)
        explorer.files_segment_requested.connect(self._open_new_view_for_files)

        # 若後續程式有用到 self.fs_model / self.tree，做相容別名
        self.left_dock = explorer
        self.fs_model = explorer.model
        self.tree = explorer.tree
        self.act_toggle_dock = self.left_dock.toggleViewAction()

    def _on_tree_double_clicked(self, index) -> None:
        p = Path(self.fs_model.filePath(index))
        if not p.is_file():
            return

        img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".gif", ".webp"}
        if p.suffix.lower() in img_exts:
            try:
                self.idx = self.image_paths.index(p)
            except ValueError:
                self.image_paths = [p]
                self.idx = 0
                self.cache.clear()
            self._load_current_image(recompute=True)
        else:
            # 與 MediaExplorer 的清單統一，但分割檢視僅載入圖片
            self.status.message_temp(f"僅支援圖片檔案：{p.name}", 3000)

    # ---- load / recompute ----

    def _load_current_image(self, recompute: bool = False) -> None:
        if not self.image_paths:
            return
        path = self.image_paths[self.idx]
        if recompute or path not in self.cache:
            # ★ 改用科幻彈窗，而非底部忙碌或 QProgressDialog
            self.status.start_scifi(f"分割中：{Path(path).name}")
            try:
                try:
                    bgr, masks, scores = self.compute_masks_fn(
                        path,
                        int(self.params["points_per_side"]),
                        float(self.params["pred_iou_thresh"]),
                    )
                except Exception:
                    logger.exception("影像分割失敗: %s", path)
                    QMessageBox.critical(self, "分割失敗", f"無法分割：{Path(path).name}")
                    return
                H, W = bgr.shape[:2]
                self.status.set_image_resolution(W, H)
                self.status.set_cursor_xy(None, None)  # 先清空游標座標
            finally:
                self.status.stop_scifi()

            masks = [(m > 0).astype(np.uint8) for m in masks]
            self.cache[path] = (bgr, masks, scores)

        self.selected_indices.clear()
        self._hover_idx = None
        self._update_canvas()
        self._update_selected_count()
        self._update_nav_buttons()
        self.status.message(
            f"載入完成：{Path(path).name}，共有 {len(self.cache[path][1])} 個候選遮罩"
        )

    def _apply_params(self) -> None:
        pps = int(self.spn_points.value())
        iou = float(self.spn_iou.value())
        self.params["points_per_side"] = pps
        self.params["pred_iou_thresh"] = iou
        self._load_current_image(recompute=True)
        self.status.message_temp("參數已套用", 1800)

    # 若你有「視圖置入」按鈕或勾選, 也寫回
    def on_fit_on_open_toggled(self, on: bool):
        self.params["fit_on_open"] = bool(on)

    # ---- navigation ----
    def _update_nav_buttons(self) -> None:
        n = len(self.image_paths)
        self.btn_prev.setEnabled(self.idx > 0 and n > 0)
        self.btn_next.setEnabled(self.idx < n - 1 and n > 0)

    def _prev_image(self) -> None:
        if self.idx > 0:
            self.idx -= 1
            self._load_current_image(recompute=False)

    def _next_image(self) -> None:
        if self.idx < len(self.image_paths) - 1:
            self.idx += 1
            self._load_current_image(recompute=False)

    # ---- mapping / hit ----
    def _map_widget_to_image(self, p: QPoint) -> Optional[Tuple[int, int]]:
        return self.view.map_widget_to_image(p)

    def _hit_test_xy(self, masks: List[np.ndarray], x: int, y: int) -> Optional[int]:
        if not masks:
            return None
        if y < 0 or y >= masks[0].shape[0] or x < 0 or x >= masks[0].shape[1]:
            return None
        hits = [i for i, m in enumerate(masks) if m[y, x] > 0]
        if not hits:
            return None
        areas = [(i, int(masks[i].sum())) for i in hits]
        areas.sort(key=lambda t: t[1])
        return areas[0][0]

    # ---- draw ----
    def _update_canvas(self) -> None:
        path = self.image_paths[self.idx]
        bgr, masks, _ = self.cache[path]
        base = bgr.copy()

        # 顯示模式: 0=遮罩, 1=BBox
        disp_id = self.display_group.checkedId() if hasattr(self, "display_group") else 0
        use_bbox = disp_id == 1

        # 輸出模式: 0=個別, 1=聯集
        mode_id = self.mode_group.checkedId() if hasattr(self, "mode_group") else 0
        is_union = mode_id == 1

        if not use_bbox:
            # 遮罩高亮模式
            if self.selected_indices:
                sel_union = np.zeros(base.shape[:2], dtype=np.uint8)
                for i in self.selected_indices:
                    if 0 <= i < len(masks):
                        sel_union = np.maximum(sel_union, masks[i])
                m = sel_union > 0
                base[m] = (base[m] * 0.4 + np.array([0, 255, 0]) * 0.6).astype(np.uint8)

            if self._hover_idx is not None and 0 <= self._hover_idx < len(masks):
                m = masks[self._hover_idx] > 0
                base[m] = (base[m] * 0.2 + np.array([0, 255, 0]) * 0.8).astype(np.uint8)
                contours, _ = cv2.findContours(
                    m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                if contours:
                    cv2.polylines(base, contours, True, (0, 255, 0), 2)

        else:
            # BBox 模式
            H, W = base.shape[:2]
            if is_union and self.selected_indices:
                # 聯集 + BBox: 只畫一個框線
                union_mask = np.zeros((H, W), dtype=np.uint8)
                for i in self.selected_indices:
                    if 0 <= i < len(masks):
                        union_mask = np.maximum(union_mask, masks[i])
                x, y, w, h = compute_bbox(union_mask > 0)
                cv2.rectangle(base, (x, y), (x + w, y + h), (0, 255, 0), 3)
            else:
                # 個別 + BBox: 已選畫細線, 懸浮畫粗線
                for i in self.selected_indices:
                    if 0 <= i < len(masks):
                        x, y, w, h = compute_bbox(masks[i] > 0)
                        cv2.rectangle(base, (x, y), (x + w, y + h), (0, 255, 0), 2)
                if self._hover_idx is not None and 0 <= self._hover_idx < len(masks):
                    x, y, w, h = compute_bbox(masks[self._hover_idx] > 0)
                    cv2.rectangle(base, (x, y), (x + w, y + h), (0, 255, 0), 3)

        if hasattr(self, "status"):
            self.status.set_display_info(
                "BBox" if use_bbox else "遮罩", is_union, len(self.selected_indices)
            )
        self.view.set_image_bgr(base)

    def _update_selected_count(self) -> None:
        self.lbl_selected.setText(f"已選目標：{len(self.selected_indices)}")

    # ---- save ----
    def _save_selected(self) -> None:
        if not self.selected_indices and self._hover_idx is not None:
            ret = QMessageBox.question(
                self, "未選擇目標", "尚未選擇任何目標，是否儲存目前滑鼠指向的目標？"
            )
            if ret == QMessageBox.StandardButton.Yes:
                self._save_one(self._hover_idx)
            return
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "尚未選擇任何目標")
            return
        if self.rb_mode_union.isChecked():
            self._save_union(sorted(self.selected_indices))
        else:
            self._save_indices(sorted(self.selected_indices))

    def _save_one(self, idx: int) -> None:
        self._save_indices([idx])

    def _save_union(self, indices: List[int]) -> None:
        path = self.image_paths[self.idx]
        bgr, masks, _ = self.cache[path]
        source_name = Path(path).stem

        out_dir = None
        if self.pm:
            source_name = self.pm.get_source_name(path)
            out_dir = self.pm.get_objects_dir(source_name)
        else:
            d = QFileDialog.getExistingDirectory(self, "選擇儲存資料夾", str(Path(path).parent))
            if d:
                out_dir = Path(d)

        if not out_dir:
            self.status.message("取消儲存")
            return

        H, W = bgr.shape[:2]
        union_mask = np.zeros((H, W), dtype=np.uint8)
        for i in indices:
            if 0 <= i < len(masks):
                union_mask = np.maximum(union_mask, (masks[i] > 0).astype(np.uint8))

        base_name = "union"

        # 準備輸出影像 (BGRA)
        bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
        bgra[:, :, 3] = union_mask * 255

        if self.rb_bbox.isChecked():
            # 裁成聯集的外接矩形
            x, y, w, h = compute_bbox(union_mask > 0)
            crop = bgra[y : y + h, x : x + w]
            img_h, img_w = h, w
            # 標註以裁後影像為座標系
            boxes = [(0, 0, w, h)]
            poly = self._compute_polygon(union_mask[y : y + h, x : x + w])
            polys = [poly]
        else:
            # 原圖大小
            crop = bgra
            img_h, img_w = H, W
            x, y, w, h = compute_bbox(union_mask > 0)
            boxes = [(x, y, w, h)]
            poly = self._compute_polygon(union_mask > 0)
            polys = [poly]

        # 寫 PNG
        ok, buf = cv2.imencode(".png", crop)
        if ok:
            (out_dir / f"{base_name}.png").write_bytes(buf.tobytes())
            # 寫標註 (依勾選)
            self._write_yolo_labels(out_dir, base_name, boxes, polys, img_w, img_h)
            QMessageBox.information(self, "完成", "已儲存 1 個聯集物件")
            self.status.message("完成")
        else:
            logger.error("PNG encode 失敗: %s", out_dir / f"{base_name}.png")
            QMessageBox.warning(self, "未儲存", "沒有任何檔案被寫出")

    def _save_indices(self, indices: List[int]) -> None:
        path = self.image_paths[self.idx]
        bgr, masks, _ = self.cache[path]

        out_dir = None
        source_name = Path(path).stem
        if self.pm:
            source_name = self.pm.get_source_name(path)
            out_dir = self.pm.get_objects_dir(source_name)
        else:
            d = QFileDialog.getExistingDirectory(self, "選擇儲存資料夾", str(Path(path).parent))
            if d:
                out_dir = Path(d)

        if not out_dir:
            self.status.message("取消儲存")
            return

        saved = 0
        H, W = bgr.shape[:2]

        for i in indices:
            if not (0 <= i < len(masks)):
                continue
            m = masks[i] > 0

            # 準備輸出影像 (BGRA)
            bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
            bgra[:, :, 3] = m.astype(np.uint8) * 255

            base_name = f"{i:03d}"

            if self.rb_bbox.isChecked():
                # 裁成該物件的最小外接矩形
                x, y, w, h = compute_bbox(m)
                crop = bgra[y : y + h, x : x + w]
                img_h, img_w = h, w
                # 對應的標註：以裁後影像為座標系
                boxes = [(0, 0, w, h)]
                poly = self._compute_polygon(m[y : y + h, x : x + w])
                polys = [poly]
            else:
                # 原圖大小
                crop = bgra
                img_h, img_w = H, W
                x, y, w, h = compute_bbox(m)
                boxes = [(x, y, w, h)]
                poly = self._compute_polygon(m)
                polys = [poly]

            # 寫 PNG
            ok, buf = cv2.imencode(".png", crop)
            if ok:
                (out_dir / f"{base_name}.png").write_bytes(buf.tobytes())
                saved += 1
                # 寫標註 (依勾選)
                self._write_yolo_labels(out_dir, base_name, boxes, polys, img_w, img_h)
            else:
                logger.error("PNG encode 失敗: %s", out_dir / f"{base_name}.png")

        if saved:
            QMessageBox.information(self, "完成", f"已儲存 {saved} 個物件")
            self.status.message("完成")
        else:
            QMessageBox.warning(self, "未儲存", "沒有任何檔案被寫出")

    # ---- event filter on view viewport ----
    def eventFilter(self, obj, event):
        if obj is self.view.viewport():
            try:

                def _pt(ev):
                    return ev.position().toPoint() if hasattr(ev, "position") else ev.pos()

                if event.type() == QEvent.MouseMove:
                    pos = _pt(event)
                    img_xy = self._map_widget_to_image(pos)
                    if img_xy is None:
                        if self._hover_idx is not None:
                            self._hover_idx = None
                            self._update_canvas()
                        self.status.set_cursor_xy(None, None)  # 清空
                    else:
                        x, y = img_xy
                        path = self.image_paths[self.idx]
                        _, masks, _ = self.cache[path]
                        self._hover_idx = self._hit_test_xy(masks, x, y)
                        self._update_canvas()
                        self.status.set_cursor_xy(x, y)  # 即時更新游標座標
                    return False
                if event.type() == QEvent.MouseButtonPress:
                    pos = _pt(event)
                    img_xy = self._map_widget_to_image(pos)
                    if img_xy is None:
                        return False
                    x, y = img_xy
                    path = self.image_paths[self.idx]
                    _, masks, _ = self.cache[path]
                    tgt = self._hit_test_xy(masks, x, y)
                    if tgt is None:
                        return False
                    if event.button() == Qt.MouseButton.LeftButton:
                        self.selected_indices.add(tgt)
                        self._update_selected_count()
                        self._update_canvas()
                    elif event.button() == Qt.MouseButton.RightButton:
                        if tgt in self.selected_indices:
                            self.selected_indices.remove(tgt)
                            self._update_selected_count()
                            self._update_canvas()
                    return False
            except Exception:
                logger.warning("滑鼠事件處理發生例外", exc_info=True)
                return False
        return super().eventFilter(obj, event)

    # 新增：在 SegmentationViewer 類別中加入兩個 helper
    def _collect_images_with_pivot_first(self, pivot: Path) -> List[Path]:
        exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".gif", ".webp"}
        imgs = [
            p for p in sorted(pivot.parent.glob("*")) if p.is_file() and p.suffix.lower() in exts
        ]
        pv = pivot.resolve() if hasattr(pivot, "resolve") else pivot
        head = [p for p in imgs if (p.resolve() if hasattr(p, "resolve") else p) == pv]
        tail = [p for p in imgs if (p.resolve() if hasattr(p, "resolve") else p) != pv]
        return (head or [pivot]) + tail

    def _open_new_view_for_files(self, paths: list[str]) -> None:
        if not paths:
            return
        for s in paths:
            p = Path(s)
            if not p.exists() or not p.is_file():
                continue
            imgs = self._collect_images_with_pivot_first(p)
            v = SegmentationViewer(
                None,  # 改為獨立最上層視窗
                imgs,
                self.compute_masks_fn,
                params_defaults=self.params,  # 沿用當前視窗設定
                title=f"自動分割檢視（{p.name}）",
            )
            v.setAttribute(Qt.WA_DeleteOnClose, True)
            v.setWindowFlag(Qt.Window, True)
            self._spawned_views.append(v)

            def _drop_ref(*_):
                try:
                    self._spawned_views.remove(v)
                except ValueError:
                    pass

            v.destroyed.connect(_drop_ref)
            v.show()
            v.raise_()
            v.activateWindow()

    def save_union_hotkey(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "尚未選擇任何目標")
            return
        self._save_union(sorted(self.selected_indices))

    # [新增] 放在 SegmentationViewer 類別內其它私有方法旁

    def _compute_polygon(self, mask: np.ndarray) -> Optional[np.ndarray]:
        """回傳最大連通域的外輪廓座標，形狀為 (N,2)，整數像素座標。"""
        m = (mask > 0).astype(np.uint8)
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None
        c = max(cnts, key=cv2.contourArea)
        return c.reshape(-1, 2)  # (N,2)

    def _write_yolo_labels(
        self,
        out_dir: Path,
        base_name: str,
        boxes: List[Tuple[int, int, int, int]],
        polys: List[Optional[np.ndarray]],
        img_w: int,
        img_h: int,
    ) -> None:
        """依勾選輸出 YOLO 檢測與/或 YOLO 分割標註檔。兩者同時勾選時各自輸出到不同檔名。"""
        cls_id = int(self.spn_cls.value()) if hasattr(self, "spn_cls") else 0

        # YOLO 檢測: 每行 => cls xc yc w h (皆為 0~1)
        if getattr(self, "chk_yolo_det", None) and self.chk_yolo_det.isChecked():
            lines = []
            for x, y, w, h in boxes:
                if w <= 0 or h <= 0:
                    continue
                xc = (x + w / 2.0) / img_w
                yc = (y + h / 2.0) / img_h
                nw = w / img_w
                nh = h / img_h
                lines.append(f"{cls_id} {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}")
            if lines:
                (out_dir / f"{base_name}_yolo.txt").write_text("\n".join(lines), encoding="utf-8")

        # YOLO 分割: 每行 => cls x1 y1 x2 y2 ... (座標皆為 0~1)
        if getattr(self, "chk_yolo_seg", None) and self.chk_yolo_seg.isChecked():
            lines = []
            for poly in polys:
                if poly is None or len(poly) == 0:
                    continue
                pts = []
                for px, py in poly:
                    pts.append(f"{px / img_w:.6f} {py / img_h:.6f}")
                lines.append(f"{cls_id} " + " ".join(pts))
            if lines:
                (out_dir / f"{base_name}_seg.txt").write_text("\n".join(lines), encoding="utf-8")
