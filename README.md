# WEBCAM-SNAPPER

以 PySide6 打造的輕量相機工具。提供相機裝置選擇、一般拍照、連拍、錄影，以及可收放/浮動的檔案瀏覽器，支援直接刪除與重新命名檔案。以模組化(Class + 檔案分離)為核心，方便後續擴充與維護。

---

## 特色功能

- **相機裝置選擇**: 啟用前即可從下拉選單選擇要使用的相機。
- **一般拍照**: 快速擷取單張影像，檔名以時間戳記生成。
- **連拍(Burst)**: 可設定張數與間隔(ms)自動連續擷取。
- **錄影**: 開始/暫停/停止，並統一以單一狀態列顯示錄影狀態。
- **檔案瀏覽器(Media Explorer)**:
  - 左側 Dock，可收放、可拖出成獨立視窗、可一鍵合併回主視窗。
  - 列出輸出資料夾內的圖片與影片，支援刪除與重新命名。
  - 關閉 Dock 後，主畫面的「檔案瀏覽」按鈕狀態會同步更新。
- **模組化架構**: 拍照、連拍、錄影、檔案瀏覽器與共用工具拆分獨立檔案，維護清晰。

---

## 專案結構

<details>
<summary><b>點我展開/收合：專案樹狀結構</b></summary>

~~~text
D:\AI\WEBCAM-SNAPPER
│  .gitignore
│  LICENSE
│  main.py
│
├─modules
│  │  burst.py        # 連拍控制 BurstShooter
│  │  explorer.py     # 檔案瀏覽器 MediaExplorer (Dock/浮動、刪除/重新命名)
│  │  photo.py        # 一般拍照 PhotoCapture
│  │  recorder.py     # 錄影控制 VideoRecorder
│  │
│  └─__pycache__
│          ...
│
└─utils
        utils.py       # 公用函式(路徑/檔名時間戳等)
~~~

</details>

> 依賴元件: PySide6(Qt6 Multimedia)。FFmpeg 後端由 QtMultimedia 整合，Windows 平台通常可直接使用。

---

## 安裝與執行

### 1) 環境需求

- Python 3.9~3.12 (建議 3.11)
- Windows 10/11 (其他平台可自行測試)
- 套件: `PySide6`

### 2) 安裝步驟 (Windows PowerShell)

```bash
# 建議使用虛擬環境
python -m venv .venv
.\.venv\Scripts\activate

# 安裝必要套件
pip install --upgrade pip
pip install PySide6
