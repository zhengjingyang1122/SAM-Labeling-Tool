# modules/sam_engine.py
import logging
from pathlib import Path

import cv2
import numpy as np
import torch
from segment_anything import SamAutomaticMaskGenerator, SamPredictor, sam_model_registry

logger = logging.getLogger(__name__)


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
        img_path = Path(img_path)
        bgr = self._read_image_bgr(img_path)
        if bgr is None or bgr.size == 0:
            raise FileNotFoundError(f"讀取影像失敗，請確認檔案存在且可讀: {img_path}")
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
            logger.error("讀取影片第一幀失敗: %s", video_path)
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
            logger.warning("釋放 GPU 記憶體時發生例外（忽略）", exc_info=True)

    def is_loaded(self) -> bool:
        return self._sam is not None

    # 加到 SamEngine 類別內

    def embedding_path_for(self, img_path: Path) -> Path:
        p = Path(img_path)
        return p.with_suffix(p.suffix + ".sam_embed.npz")

    def masks_cache_path_for(self, img_path: Path) -> Path:
        p = Path(img_path)
        return p.with_suffix(p.suffix + ".sam_masks.npz")

    def has_embedding(self, img_path: Path) -> bool:
        return self.embedding_path_for(img_path).exists()

    # 加到 SamEngine 類別內

    def auto_masks_from_image_cached(
        self, img_path: Path, points_per_side=32, pred_iou_thresh=0.88
    ):
        self._ensure_loaded()
        img_path = Path(img_path)
        mask_p = self.masks_cache_path_for(img_path)

        # 1) 有快取就直接讀
        if mask_p.exists():
            data = np.load(str(mask_p), allow_pickle=True)
            bgr = cv2.imread(str(img_path))
            masks_arr = data["masks"]  # shape: [N, H, W], uint8
            masks = [masks_arr[i].astype(np.uint8) for i in range(masks_arr.shape[0])]
            scores = data["scores"].astype(np.float32).tolist()
            return bgr, masks, scores

        # 2) 沒有快取就計算
        bgr, masks, scores = self.auto_masks_from_image(
            img_path, points_per_side=points_per_side, pred_iou_thresh=pred_iou_thresh
        )

        # 2a) 寫出 masks 快取
        np.savez_compressed(
            str(mask_p),
            masks=np.array(masks, dtype=np.uint8),
            scores=np.array(scores, dtype=np.float32),
        )

        # 2b) 嘗試寫出 embedding（即使失敗也不影響使用）
        try:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            predictor = SamPredictor(self._sam)
            predictor.set_image(rgb)
            emb = predictor.get_image_embedding().cpu().numpy()
            original_size = np.array(predictor.original_size, dtype=np.int32)
            input_size = np.array(predictor.input_size, dtype=np.int32)
            emb_p = self.embedding_path_for(img_path)
            np.savez_compressed(
                str(emb_p),
                embedding=emb.astype(np.float32),
                original_size=original_size,
                input_size=input_size,
                image_shape=np.array(rgb.shape[:2], dtype=np.int32),
            )
        except Exception:
            logger.warning("寫入 SAM embedding 失敗（略過不影響使用）: %s", img_path, exc_info=True)

        return bgr, masks, scores

    def _read_image_bgr(self, img_path: Path):
        """
        穩健讀入影像為 BGR。避免 Windows 上含中文或特殊字元路徑造成 imread 失敗。
        回傳: np.ndarray 或 None
        """
        try:
            # 以 bytes 讀檔，再用 imdecode，最穩定也最能處理 Unicode 路徑
            data = img_path.read_bytes()
            arr = np.frombuffer(data, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                return img
        except Exception as e:
            logger.warning("以 imdecode 讀取影像失敗: %s | %s", img_path, e)

        # 後備方案：傳統 imread
        try:
            img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            logger.error("以 imread 讀取影像失敗: %s | %s", img_path, e)
            return None
