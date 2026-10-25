# 歷史示範素材

本目錄精選原作業資料夾的兩組既有輸入與輸出，共 8 個媒體檔、19,430,750 bytes（18.53 MiB）。未修改或重新編碼，SHA-256 已與原檔核對。以下來源路徑相對於原始 `ADIPHW` 資料夾，不代表此儲存庫包含完整資料集。

## 如何看示範

直接開啟 [示範頁](index.html)，或分別查看下列影像與短片。`auto` 為歷史自動模式輸出，`multi` 為歷史多框選模式輸出；單物件範例也保留多框模式結果供比較。

| 範例 | 原圖 | 自動模式 | 多框選模式 | 短片 |
|---|---|---|---|---|
| 單物件：燈塔 | [input.png](single/input.png) | [auto.jpg](single/auto.jpg) | [multi.jpg](single/multi.jpg) | [demo.mp4](single/demo.mp4) |
| 多物體：飛機、巴士與登機橋 | [input.jpg](multiple/input.jpg) | [auto.jpg](multiple/auto.jpg) | [multi.jpg](multiple/multi.jpg) | [demo.mp4](multiple/demo.mp4) |

這些是歷史作業成果，尚未證實由儲存庫目前程式版本產生，不保證新版逐像素重現。輸出仍看得出框選邊緣與分割不完整，適合展示課程實作，不代表精確深度估測。

## 檔案驗證

- 六張圖片均可解碼。單物件組為 512×768；多物體組為 3089×2048。
- 兩段影片均經 OpenCV 完整逐幀讀取，實讀 150／標示 150 幀，30 FPS、5 秒。
- 單物件影片：512×768，`avc1`。多物體影片：3088×2048，`mp4v`；比原圖少一欄像素。
- 部分瀏覽器可能無法直接播放 `mp4v`，可下載後用相容播放器觀看；副檔名 MP4 不保證瀏覽器支援。

## 來源與雜湊

完整機器可讀清單另見 [manifest.json](manifest.json)。

| 本目錄路徑 | 原來源相對路徑 | bytes | SHA-256 |
|---|---|---:|---|
| `single/input.png` | `ADIP Final dataset/單物件平滑背景/0019.png` | 671476 | `b7450b264b1b0a411390d8931b112c27905a992520fc90569dc4b920aa32bbdc` |
| `single/auto.jpg` | `結果呈現/單物件平滑背景/19/19_depth_field_result_auto.jpg` | 79305 | `2a20b94610c2b4b488532a565b3ce262a471937a2ac8ff5f8e22eba9b6f43c6b` |
| `single/multi.jpg` | `結果呈現/單物件平滑背景/19/19_depth_field_result_multil.jpg` | 70399 | `d1cb5e6fd5c19d7392f44c6eab3f1bc83114c76594df9a9252c9cf52ade90c78` |
| `single/demo.mp4` | `結果呈現/單物件平滑背景/19/19_Short_Video_Result.mp4` | 4494302 | `53ad399df75fc1af972f86adefbfbdab132f41cdaad28936b4e19ea14bbabafd` |
| `multiple/input.jpg` | `ADIP Final dataset/多物體平滑背景/25.jpg` | 1095630 | `94bab74661d2543520048484badc108b422a0e55184d8ca40e0354f3ae02fc68` |
| `multiple/auto.jpg` | `結果呈現/多物體平滑背景/25/25_depth_field_result_auto.jpg` | 1022836 | `27d2b24707f7faded6cbe01888ed3e9fb51d5bcc762759fe10554e6f5252ef9e` |
| `multiple/multi.jpg` | `結果呈現/多物體平滑背景/25/25_depth_field_result_multil.jpg` | 835173 | `29c293471acbae3e4c2fb11bd73f93ed4761a2659322dbdc307fc909b0856adf` |
| `multiple/demo.mp4` | `結果呈現/多物體平滑背景/25/25_Short_Video_Result.mp4` | 11161629 | `262f74a1ecc3006814e3e414ddc1236ad6554fc3a15e53bbfe2f79c57b675511` |

## 素材權利

原始資料夾未附影像及影片來源、作者或授權文件，不能據此認定素材可任意再利用。此處保留作業示範關係，影像及其衍生輸出不自動適用程式碼的授權；再次散布或其他用途前，請先確認原素材權利。

未收錄完整資料集、其他課程作業、成績文件或含明顯人臉／車牌的候選素材。
