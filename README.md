# Webcam Snapper - Modular Edition

以 PySide6 建構的桌面相機工具. 提供相機裝置選擇, 單張拍照, 連拍, 錄影, 左側可收放的檔案瀏覽器, 以及基於 目標分割(Segment Anything, SAM) 的影像自動分割與透明背景輸出. 採模組化(Class 與檔案分離)設計, 便於擴充與維護.

---

## 目錄

- [Webcam Snapper - Modular Edition](#webcam-snapper---modular-edition)
  - [目錄](#目錄)
  - [特色功能](#特色功能)
  - [畫面概覽](#畫面概覽)
  - [安裝](#安裝)
    - [系統需求](#系統需求)
    - [依賴套件](#依賴套件)
    - [安裝步驟](#安裝步驟)
  - [執行方式](#執行方式)
  - [使用流程](#使用流程)
  - [SAM 自動分割詳解](#sam-自動分割詳解)
  - [鍵盤快捷鍵](#鍵盤快捷鍵)
  - [日誌與 UI 提示](#日誌與-ui-提示)
  - [檔案結構](#檔案結構)
  - [開發與擴充](#開發與擴充)
  - [常見問題 FAQ](#常見問題-faq)
  - [授權 License](#授權-license)
  - [貢獻與提交訊息](#貢獻與提交訊息)

---

## 特色功能

- 即時相機預覽與裝置選擇. 以 QtMultimedia 建立 Camera Session 並輸出到 QVideoWidget, 同時配置 QImageCapture 拍照與 QMediaRecorder 錄影. 預設嘗試 MPEG4 容器, H264 視訊與 AAC 音訊.
- 單張拍照與具重試機制的安全寫檔. 當相機尚未就緒時會以 QTimer 進行延遲重試, 失敗會寫入日誌. 檔名使用時間戳.
- 連拍(Burst). 可設定張數與間隔毫秒, 首張立即拍攝後以計時器節奏進行, 完成時寫入結束資訊.
- 錄影. 支援開始或繼續, 暫停, 停止, 自動給定輸出路徑與檔名. 錯誤會記錄並通知.
- 檔案瀏覽器(Media Explorer). 左側 Dock 可收放或浮動, 顯示圖片與影片, 支援重新命名與刪除, 右鍵選單可對圖片觸發自動分割. 另提供取得最近一張影像或最近一段影片的 API.
- 影像自動分割與透明輸出. 以 目標分割(Segment Anything, SAM) 模型產生多個遮罩候選, 支援游標指向預覽, 左鍵加入選取, 右鍵移除, 可個別輸出或取聯集, 並以 最小外接矩形 或 原圖尺寸 輸出 PNG 含透明度通道. 聯集輸出附形態學開閉運算與最大連通區篩選.
- 模型快取與加速. 自動分割支援遮罩快取與影像 embedding 快取, 下次開啟同圖時可快速載入. 模型可卸載釋放 GPU 記憶體.
- 狀態列與科幻進度彈窗. 統一底部狀態列顯示訊息與進度, 並提供半透明霓虹風彈窗與模擬進度, 另可顯示影像尺寸與滑鼠座標.
- 鍵盤快捷鍵與客製化. 內建 Space 拍照, R 錄影開始或繼續, Shift+R 停止, F9 切換 Dock, 影像檢視器另有分頁導覽與儲存快捷鍵. 支援從 JSON 讀取自訂快捷鍵, 亦可於 UI 顯示快捷鍵一覽.
- 首次啟動導覽與說明選單. 提供快速導覽精靈, 說明選單包含 快速導覽, 鍵盤快捷鍵, 開啟日誌資料夾.
- 統一日誌(logging)與 UI 提示. 內含 PII 去識別化過濾器, JSON 及文字檔案輪替, 並將 Python 與 Qt 訊息導入日誌. UI 會在錯誤時顯示狀態與節流後的彈窗.

---

## 畫面概覽

- 右側控制區: 輸出路徑, 相機裝置與啟停, 拍照與連拍, 錄影, 模型預載, 自動分割. 中間為相機預覽.
- 左側 Dock: 檔案瀏覽器, 可顯示與管理輸出資料夾中的媒體.

---

## 安裝

### 系統需求

- Python 3.9~3.12 建議 3.11.
- Windows 10 或 11. 其他平台可自行測試.
- 顯示卡若要使用 GPU 推論: 安裝對應的 CUDA 版 PyTorch.

### 依賴套件

- PySide6
- opencv-python
- numpy
- torch
- segment-anything

### 安裝步驟

~~~bash
# 建議使用虛擬環境
python -m venv .venv
.\.venv\Scripts\activate

pip install --upgrade pip
pip install PySide6 opencv-python numpy torch
# 安裝 Segment Anything
pip install git+https://github.com/facebookresearch/segment-anything.git
~~~

> 若不使用自動分割功能, 可不安裝 torch 與 segment-anything.

---

## 執行方式

~~~bash
python main.py
~~~

第一次啟動會出現快速導覽精靈與裝置掃描. 下次可從選單 說明 快速導覽 再次開啟.

---

## 使用流程

1. 指定輸出資料夾. 於右側 輸出路徑 區塊輸入或點選 瀏覽. 偏好會自動保存. 檔名使用時間戳自動生成.
2. 選擇相機並啟動. 於 相機設備 選擇下拉後按 啟動相機. 預覽即時顯示.
3. 拍照. 點 拍一張 或按 Space. 檔案會出現在輸出資料夾, 左側瀏覽器可立即查看.
4. 連拍. 設定 張數 與 間隔 毫秒, 點 開始連拍. 可隨時停止.
5. 錄影. 點 開始或繼續 開始錄影, 暫停, 或 停止 後自動儲存. 錄影格式嘗試 MPEG4 H264 AAC.
6. 管理檔案. 左側瀏覽器支援 刪除 與 重新命名, 亦可右鍵啟動 自動分割.
7. 影像自動分割. 於右側點 自動分割 開啟選單, 可分別選擇 單一影像 或 資料夾 批次. 首次使用需載入 SAM 權重. 檢視器中以滑鼠選取欲輸出目標, 再按 儲存已選目標.
8. 模型預載與下載. 勾選 預先載入 SAM 模型 可互動式載入模型, 預設檔案路徑為 models/sam_vit_h_4b8939.pth. 若不存在, 會詢問是否下載約 2.5GB 權重並顯示百分比進度.

---

## SAM 自動分割詳解

- 引擎 SamEngine. 以 sam_model_registry 建立模型並移動至 cuda 或 cpu, 提供影像與影片第一幀自動遮罩. 回傳遮罩與分數.
- 快取機制. 為每張影像寫入 .sam_masks.npz 與 .sam_embed.npz 快取, 後續開啟可快速載入遮罩與 embedding.
- 檢視器 SegmentationViewer.
  - 互動: 滑鼠移動顯示 hover 遮罩, 左鍵加入選取, 右鍵移除. 狀態列同步顯示游標座標與影像尺寸.
  - 儲存: 可個別輸出或聯集輸出. 聯集輸出附開閉運算與最大連通區過濾, 並支援 最小外接矩形 或 原圖大小 輸出含透明度 PNG.
  - 熱鍵: 支援上一張與下一張, 儲存快捷鍵, 以及 F9 切換 Dock.

---

## 鍵盤快捷鍵

預設快捷鍵如下, 可由 shortcuts.json 覆寫.

Main 範圍:

- Space: 拍照 capture.photo
- R: 錄影開始或繼續 record.start_resume
- Shift+R: 停止錄影 record.stop_save
- F9: 切換檔案 Dock dock.toggle

Viewer 範圍:

- Left 或 PageUp: 前一張 nav.prev
- Right 或 PageDown: 下一張 nav.next
- S 或 Ctrl+S: 儲存已選 save.selected
- U: 聯集輸出 save.union
- F9: 切換 Dock
- Esc: 關閉視窗

版本庫也附一份 shortcuts.json 範例供參考.

---

## 日誌與 UI 提示

- 檔案輸出: logs/app.log 與 logs/app.jsonl 輪替. 支援 JSON 格式與去識別化, 包含 email, phone, 統一編號等防誤曝.
- UI 串接: 任何 logging.WARNING 以上訊息會顯示於狀態列, ERROR 以上可彈窗, 具節流與去重. 可於偏好設定調整 popup level 與節流毫秒.
- Qt 訊息代理: 將 Qt 的警告與錯誤導入 Python logging.
- 主程式初始化時讀取偏好並安裝日誌與 UI handler. 說明選單提供 開啟日誌資料夾 以利除錯.

---

## 檔案結構

~~~text
.
├─ main.py                        # 入口點與主視窗組裝
├─ actions.py                     # UI 槽函式與業務邏輯, SAM 與分割工作流程
├─ burst.py                       # 連拍控制 BurstShooter
├─ camera_manager.py              # 相機與錄影 Session 封裝
├─ explorer.py                    # 檔案瀏覽器 Dock
├─ explorer_controller.py         # Dock 切換與路徑同步控制
├─ logging_setup.py               # 日誌設定與 UI 橋接
├─ onboarding.py                  # 快速導覽精靈
├─ photo.py                       # 單張拍照與重試

├─ recorder.py                    # 錄影控制 VideoRecorder
├─ sam_engine.py                  # SAM 推論與快取
├─ segmentation_viewer.py         # 分割檢視器與互動輸出
├─ shortcuts.py                   # 快捷鍵管理與對話框
├─ status_footer.py               # 統一狀態列與科幻進度彈窗
├─ ui_main.py                     # 主視窗 UI 元件佈局與 wire-up
├─ ui_state.py                    # 控制項可用狀態切換
├─ utils.py                       # 路徑, 檔名, 時間戳工具

├─ shortcuts.json                 # 快捷鍵覆寫檔
└─ README.md
~~~

---

## 開發與擴充

- 熱鍵註冊: 於主視窗建立時註冊 Main 範圍, 在分割檢視器註冊 Viewer 範圍. 可透過全域管理器集中管理.
- Dock 控制: ExplorerController 封裝顯示與可視狀態同步, 例外時記錄 warning 或 error.
- UI 狀態: 依相機與連拍狀態切換按鈕可用性.
- 分割流程: Actions 整合自動分割選單, 權重載入/下載, 與開啟 SegmentationViewer 視窗.

---

## 常見問題 FAQ

- 啟動相機失敗: 請確認相機未被其他程式占用, 嘗試更換裝置或權限. 失敗訊息會彈窗並寫入日誌. 可於 說明 開啟日誌資料夾 查看詳情.
- 錄影沒有 H264 或 AAC: 某些平台或編碼器不可用, 程式會盡力設定, 若失敗會記錄 warning 並使用可用設定.
- SAM 權重過大無法下載: 可手動將 sam_vit_h_4b8939.pth 放入 models 目錄, 在 UI 中勾選 預先載入 SAM 模型. 若仍失敗可於對話框選擇已有的 .pth 檔.
- 記憶體不足: 可關閉預載或在分割後卸載模型以釋放 GPU 記憶體.

---

## 授權 License

請在此補上專案授權條款.

---

## 貢獻與提交訊息

- 歡迎以 約定式提交(Conventional Commits) 撰寫 Commit 訊息, 建議搭配 Gitmoji 標示.
- 新增功能或修正: 建議以模組化方式擴充, 並在 main.py 掛載或注入相依.
- 建議 PR 模板包含 動機, 變更內容, 測試方式, 風險評估 與 截圖/錄影.
"
