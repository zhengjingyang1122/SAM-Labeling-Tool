# modules/prefs.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

_DEFAULTS: Dict[str, Any] = {
    "output_dir": "",
    "camera": {
        "preferred_device": "",  # 以裝置名稱或唯一描述識別
        "resolution": [0, 0],  # [W, H], 0 代表未指定
    },
    "sam": {
        "points_per_side": 32,
        "pred_iou_thresh": 0.88,
    },
    "viewer": {
        "fit_on_open": True,  # 開啟時自動置入視窗
        "union_morph": {
            "enabled": True,  # 聯集輸出時進行開/閉優化
            "scale": 0.003,  # 核大小比例, 隨影像最短邊 * scale
        },
    },
}


class Prefs:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else Path("config/prefs.json")
        self._data: Dict[str, Any] = json.loads(json.dumps(_DEFAULTS))
        self.load()

    def load(self) -> None:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self._merge(self._data, data)
        except Exception:
            # 壞檔忽略, 保留預設
            pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        cur = self._data
        for part in key.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def set(self, key: str, value: Any, autosave: bool = True) -> None:
        cur = self._data
        parts = key.split(".")
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = value
        if autosave:
            self.save()

    def _merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> None:
        for k, v in update.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                self._merge(base[k], v)
            else:
                base[k] = v


# 全域單例存取
from PySide6.QtWidgets import QApplication


def get_prefs() -> Prefs:
    app = QApplication.instance()
    obj = app.property("app_prefs")
    if not isinstance(obj, Prefs):
        obj = Prefs()
        app.setProperty("app_prefs", obj)
    return obj
