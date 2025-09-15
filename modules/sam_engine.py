# modules/sam_engine.py 內【新增匯入或方法】（只列新增/修改段）
# 【2】第三方安裝
from pathlib import Path

import cv2
import numpy as np
import torch
from segment_anything import SamAutomaticMaskGenerator, sam_model_registry


class SamEngine:
    def __init__(self, ckpt: Path, model_type="vit_h", device=None):
        self.ckpt = Path(ckpt)
        self.model_type = model_type
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._sam = None

    def _ensure_loaded(self):
        if self._sam is None:
            self._sam = sam_model_registry[self.model_type](checkpoint=str(self.ckpt))
            self._sam.to(self.device)

    def auto_masks_from_image(self, img_path: Path, points_per_side=32, pred_iou_thresh=0.88):
        self._ensure_loaded()
        bgr = cv2.imread(str(img_path))
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        amg = SamAutomaticMaskGenerator(
            self._sam, points_per_side=points_per_side, pred_iou_thresh=pred_iou_thresh
        )
        ms = amg.generate(rgb)
        masks = [m["segmentation"].astype(np.uint8) for m in ms]
        scores = [float(m.get("predicted_iou", 0.0)) for m in ms]
        return bgr, masks, scores

    def auto_masks_from_video_first_frame(self, video_path: Path, **amg_kwargs):
        cap = cv2.VideoCapture(str(video_path))
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            raise ValueError("Cannot read first frame")
        tmp = Path("__tmp_vframe__.png")
        cv2.imwrite(str(tmp), frame)
        try:
            return self.auto_masks_from_image(tmp, **amg_kwargs)
        finally:
            tmp.unlink(missing_ok=True)

    def load(self):
        self._ensure_loaded()

    def unload(self):
        # 釋放 GPU 記憶體
        self._pred = None
        self._sam = None
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def is_loaded(self) -> bool:
        return self._sam is not None
