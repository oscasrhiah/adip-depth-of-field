# 程式來源與整理紀錄

整理日期：2026-10-25。

## 版本選擇

| 原工作區位置 | 核對結果 |
| --- | --- |
| `ADIPHW Project 3 goodwork/Depth_of_field.py` | 最新可讀的完整整合應用；作為本次整理來源 |
| `ADIPHW Project 2/Depth_of_field.py` | 與 Project 3 的程式差異只有影片編碼器從 `avc1` 改為 `MJPG` |
| `最新版程式碼.txt` | 雖有「最新版」名稱，實際與 Project 2 位元組相同 |
| `Project_result/temporary4_canvas.py` | 較早的整合 GUI 前身 |
| `project/` 中較新的實驗腳本 | 個別演算法實驗，並非較新的完整整合應用 |
| `ADIPHW Project 4/Depth_of_field_group5.py` | 非正常 Python 文字，含 PDF 字型物件片段；未作為整理來源 |

封存原版 `archive/Depth_of_field_project3.py` 的 SHA-256：

```text
92fb039c2d8808bf4294f89389828d63eeb04d04e8ce1f655f08fa0a35454a72
```

Project 4 的打包設定與紀錄指向 `Depth_of_field.py`，目前缺少該檔。異常 `_group5.py` 並不等同於已證實的打包來源。本次沒有宣稱已恢復 Project 4。

## 整理範圍

原始作業檔案留在工作區原位置；此儲存庫為獨立副本。封存版不作啟動入口，日常執行使用根目錄 `Depth_of_field.py`。

移除未使用的 PyOpenCL 匯入，讓應用只需 OpenCV、NumPy、PyQt5；保留原本的分割、模糊與位移方法。必要的執行問題修正及驗證結果詳見 [驗證紀錄](VERIFICATION.md)。

整理版的必要修正：

- 明確指定 PyQt5 套件內的外掛目錄，避免中文虛擬環境路徑造成 Qt 平台外掛初始化失敗；建置環境另放在英數路徑。
- 移除終端除錯輸出與 tqdm 包裝，避免 CP950 無法編碼部分原有文字，以及無主控台 EXE 的輸出問題。
- 修正中央 CLAHE 區域座標；空前景與 OpenCV 分割失敗改顯示提示。
- 修正置中預覽的滑鼠座標與反向拖曳，限制預覽尺寸以避免圖片超出螢幕。
- 圖片讀寫使用 Unicode 路徑；載入新檔前清除上一張的結果與遮罩，包含載入失敗情況。
- MP4 改用 `mp4v` 編碼，檢查輸出是否能開啟及檔案是否非空，並確保釋放 writer；新增實際解碼測試。

不收錄原始數 GB 的舊 EXE、PyInstaller 中間產物、整份資料集、成績或含同學資料的文件。新 EXE 以此儲存庫程式建置，透過 Release 另行提供。
