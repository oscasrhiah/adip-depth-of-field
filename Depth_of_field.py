import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import time
import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QSlider, QProgressBar, QFileDialog, QWidget
)
from PyQt5.QtCore import Qt,QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QSpinBox, QSlider, QProgressBar, QWidget, QFileDialog
import os
import PyQt5
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import QSpinBox

# 避免 Qt 將中文安裝路徑轉成問號，明確加入套件實際外掛位置。
QCoreApplication.addLibraryPath(os.path.join(os.path.dirname(PyQt5.__file__), 'Qt5', 'plugins'))

# 全局變量
focus_rect = None  # 用於存儲用戶框選的焦點範圍
image = None  # 原始圖像
result = None  # 結果圖像
blur_strength = 50  # 默認模糊強度
desired_display_height = 1000  # 默認顯示高度，可調整
start_point = None  # 框選起始點
end_point = None  # 框選結束點
is_drawing = False  # 是否正在框選
result_window = None  # 用於存儲結果圖像窗口
blur_update_job = None  # 延遲更新的Job ID
file_path = None  # 在全局初始化
progress_bar = None  # 進度條
status_label = None  # 狀態標籤
selected_rects = []  # 用於存儲選取的多個矩形
canvas = None 

def resize_for_display(img, target_height):
    """根據目標高度等比縮放圖像"""
    height, width = img.shape[:2]
    scale = target_height / height
    new_width = int(width * scale)
    new_height = int(height * scale)
    return cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_LINEAR)


def calculate_gradient(img):
    """計算圖像的梯度幅值"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    gradient = cv2.magnitude(grad_x, grad_y)
    gradient = cv2.normalize(gradient, None, 0, 255, cv2.NORM_MINMAX)
    return gradient.astype(np.uint8)

def generate_blurred_layers(image, blur_radii):
    """生成不同模糊程度的圖層"""
    blurred_layers = []
    with ThreadPoolExecutor() as executor:
        tasks = [executor.submit(cv2.GaussianBlur, image, (r, r), 0) for r in blur_radii]
        for task in tasks:
            blurred_layers.append(task.result())
    return blurred_layers

def apply_clahe(image, rect):
    """對給定矩形區域應用CLAHE"""
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
    
    x1, y1, x2, y2 = rect
    
    # 確保 ROI 在影像範圍內
    height, width = image.shape[:2]
    if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
        raise ValueError("ROI is out of image bounds.")
    
    # 獲取感興趣區域
    roi = image[y1:y2, x1:x2]
    if roi.size == 0:
        raise ValueError("ROI is empty or not properly defined.")
    

    roi = image[y1:y2, x1:x2]
    lab = cv2.cvtColor(roi, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    l_clahe = clahe.apply(l)
    lab_clahe = cv2.merge((l_clahe, a, b))
    image[y1:y2, x1:x2] = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2RGB)

def apply_clahe_mutil(image, rects):
    """对多个矩形区域应用CLAHE"""

    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))


    height, width = image.shape[:2]
    
    # 遍历每个矩形区域
    for rect in rects:
        
        # 确保 rect 是四个数字的元组 (x, y, w, h)
        if not isinstance(rect, tuple) or len(rect) != 4:
            raise ValueError(f"矩形坐标错误，应该是 (x, y, w, h)，但获得了 {rect}，类型: {type(rect)}")
        
        # 确保矩形元素是数字
        x, y, w, h = rect
        if not all(isinstance(i, (int, float)) for i in [x, y, w, h]):
            raise ValueError(f"矩形的元素应该是数字，获得了 {rect}")
        
        # 使用整数坐标进行处理
        x1 = int(max(0, x))
        y1 = int(max(0, y))
        x2 = int(min(width, x + w))
        y2 = int(min(height, y + h))

        # 确保矩形范围有效
        if x2 <= x1:
            x2 = x1 + 1  # 确保宽度为正
        if y2 <= y1:
            y2 = y1 + 1  # 确保高度为正


        # 提取并处理该区域
        roi = image[y1:y2, x1:x2]
        lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l_clahe = clahe.apply(l)
        lab_clahe = cv2.merge((l_clahe, a, b))
        image[y1:y2, x1:x2] = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)

    return image

def grabcut_for_focus_area(image):
    """自動在圖像中央進行GrabCut並處理結果"""
    height, width = image.shape[:2]
    #cv2.imshow("debug", image)

    # 根據圖像大小設置抓取範圍為高度與寬度的一半
    rect_width = width // 2
    rect_height = height // 2
    rect_x = max(0, width // 2 - rect_width // 2)
    rect_y = max(0, height // 2 - rect_height // 2)
    rect = (rect_x, rect_y, rect_width, rect_height)

    # 初始化GrabCut掩膜
    mask = np.zeros((height, width), np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    clahe_img = image.copy()

    # 對選中的區域應用CLAHE來提高對比度
    apply_clahe(clahe_img, (rect_x, rect_y, rect_x + rect_width, rect_y + rect_height))



    # GrabCut處理
    #cv2.grabCut(image, mask, (x1, y1, x2 - x1, y2 - y1), bgd_model, fgd_model, 8, cv2.GC_INIT_WITH_RECT)
    cv2.grabCut(clahe_img, mask,rect, bgd_model, fgd_model, 10, cv2.GC_INIT_WITH_RECT)
    # 只保留前景部分


    mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')

    # 使用FloodFill進行處理，填充前景區域
    floodfill_mask = mask2.copy()
    cv2.floodFill(floodfill_mask, None, (width // 2, height // 2), 1)

    # 將掩膜應用到原始圖像
    #segmented_image = image * mask2[:, :, np.newaxis]
    #cv2.imshow("seg",segmented_image)
    # 二值化處理，將前景區域設為白色，背景區域設為黑色
    focus_mask = cv2.bitwise_and(mask2, floodfill_mask)
        # 將掩膜應用到原始圖像
    #segmented_image2 = image * focus_mask[:, :, np.newaxis]
    #cv2.imshow("seg_bitwize",segmented_image2)
    # 儲存分割出的mask
    #cv2.imwrite("J:\\ADIPHW\\mask.jpg", focus_mask)

    # 生成焦點範圍
    y, x = np.where(focus_mask == 1)
    if len(y) == 0:
        return None, focus_mask
    y1, y2 = min(y), max(y)
    x1, x2 = min(x), max(x)

    return (x1, y1, x2, y2), focus_mask

def grabcut_for_multiple_areas_with_floodfill(image, rects):
    height, width = image.shape[:2]
    clahe_img=image.copy()
    apply_clahe_mutil(clahe_img, rects)
    # 初始化
    focus_masks = []  # 用於存儲每個區域的掩膜
    focus_rects = []  # 用於存儲每個區域的外框

    # 初始化GrabCut掩膜
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)

    for rect in rects:
        # 檢查 rect 是否是 4 個數字
        if not isinstance(rect, tuple) or len(rect) != 4:
            raise ValueError(f"矩形座標錯誤，應該是 (x, y, w, h)，但獲得了 {rect}，類型: {type(rect)}")
        
        # 確保每個元素都是數字
        x, y, w, h = rect
        if not all(isinstance(i, (int, float)) for i in [x, y, w, h]):
            raise ValueError(f"矩形的元素應該是數字，獲得了 {rect}")

        # 使用整數座標進行處理
        x1 = int(max(0, x))
        y1 = int(max(0, y))
        x2 = int(min(width, x + w))
        y2 = int(min(height, y + h))

        # 確保矩形範圍有效
        if x2 <= x1:
            x2 = x1 + 1  # 確保寬度為正
        if y2 <= y1:
            y2 = y1 + 1  # 確保高度為正


        # 初始化掩膜
        mask = np.zeros((height, width), np.uint8)

        # GrabCut處理
        #print(f"GrabCut範圍: {(x1, y1, x2 - x1, y2 - y1)}")
        cv2.grabCut(clahe_img, mask, (x1, y1, x2 - x1, y2 - y1), bgd_model, fgd_model, 10, cv2.GC_INIT_WITH_RECT)

        # 生成前景掩膜
        mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')

        # FloodFill處理
        floodfill_mask = mask2.copy()
        floodfill_seed = (x1 + (x2 - x1) // 2, y1 + (y2 - y1) // 2)  # 使用矩形中心作為FloodFill的種子點
        cv2.floodFill(floodfill_mask, None, floodfill_seed, 1)

        # 合併結果
        focus_mask = cv2.bitwise_and(mask2, floodfill_mask)

        # 計算新的邊界
        y, x = np.where(focus_mask == 1)
        if len(y) > 0 and len(x) > 0:  # 如果有前景點
            y1, y2 = min(y), max(y)
            x1, x2 = min(x), max(x)
            focus_rects.append((x1, y1, x2 - x1, y2 - y1))  # 確保矩形是以 (x, y, w, h) 格式保存
            focus_masks.append(focus_mask)
    
    # 合併所有的掩膜成一個最終掩膜
    combined_mask = np.zeros((height, width), np.uint8)
    for mask in focus_masks:
        combined_mask = cv2.bitwise_or(combined_mask, mask)

    # 顯示合併後的掩膜
    #cv2.imshow("Combined Mask", combined_mask * 255)  # 顯示二值掩膜

    # 生成最終的分割圖像
    segmented_image = cv2.bitwise_and(image, image, mask=combined_mask)
    #cv2.imshow("Segmented Image", segmented_image)

    return focus_rects,  combined_mask  # 回傳合併後的掩膜focus_masks,

def is_valid_utf8(path):
    try:
        # 嘗試將路徑編碼為 utf-8
        path.encode('utf-8')
        return True
    except UnicodeEncodeError:
        return False


class DepthOfFieldApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 初始化类变量
        self.blur_strength = 50
        self.desired_display_height = 800
        self.image = None
        self.file_path = None
        self.result = None
        self.focus_mask = None
        self.rectangles = []
        self.selecting = False
        self.display_image_with_rects = None
        self.start_point = None
        self.end_point = None

        # 初始化新的变量
        self.video_duration = 5  # 默认影片长度
        self.video_fps = 30      # 默认帧率
        self.duration_input = None  # 影片长度输入框
        self.fps_input = None       # 帧率输入框

        # 初始化 UI
        self.initUI()


    def initUI(self):
        self.setWindowTitle("景深效果應用")
        self.setGeometry(100, 100, 800, 600)

        # 主窗口布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # 控制區域布局
        control_layout = QHBoxLayout()

        # 按鈕
        open_button = QPushButton("選擇圖像")
        open_button.clicked.connect(self.open_file)
        control_layout.addWidget(open_button)

        process_button = QPushButton("開始處理一")
        process_button.clicked.connect(self.process_image)
        control_layout.addWidget(process_button)

        save_button = QPushButton("保存結果")
        save_button.clicked.connect(self.save_result)
        control_layout.addWidget(save_button)

        show_button = QPushButton("顯示結果")
        show_button.clicked.connect(self.show_result_in_window)
        control_layout.addWidget(show_button)

        select_button = QPushButton("選取多物件")
        select_button.clicked.connect(self.start_selecting_objects)
        control_layout.addWidget(select_button)
        
        clear_button = QPushButton("清除選取")
        clear_button.clicked.connect(self.clear_selection)
        control_layout.addWidget(clear_button)

        process_button2 = QPushButton("開始處理二")
        process_button2.clicked.connect(self.process_multiple_areas)
        control_layout.addWidget(process_button2)

        generate_gif_button = QPushButton("生成動圖")
        generate_gif_button.clicked.connect(self.generate_gif)
        control_layout.addWidget(generate_gif_button)

        main_layout.addLayout(control_layout)

        # 增加影片參數輸入框
        video_params_layout = QHBoxLayout()

        # 影片長度
        self.duration_label = QLabel("影片長度 (秒):")
        video_params_layout.addWidget(self.duration_label)
        self.duration_input = QSpinBox()
        self.duration_input.setValue(5)  # 默認值
        self.duration_input.setMinimum(1)
        self.duration_input.setMaximum(60)  # 最大 60 秒
        #self.duration_input.setValue(5)  # 默認值
        video_params_layout.addWidget(self.duration_input)

        # 影片偵數
        self.fps_label = QLabel("影片偵數 (FPS):")
        video_params_layout.addWidget(self.fps_label)
        self.fps_input = QSpinBox()
        self.fps_input.setValue(30)  # 默認值
        self.fps_input.setMinimum(1)
        self.fps_input.setMaximum(120)  # 最大 120 FPS
        #self.fps_input.setValue(30)  # 默認值
        video_params_layout.addWidget(self.fps_input)

        main_layout.addLayout(video_params_layout)

        # 模糊強度滑動條
        self.blur_slider = QSlider(Qt.Horizontal)
        self.blur_slider.setMinimum(1)
        self.blur_slider.setMaximum(100)
        self.blur_slider.setValue(self.blur_strength)
        self.blur_slider.valueChanged.connect(self.update_blur_strength)

        self.blur_value_label = QLabel(str(self.blur_strength))
        main_layout.addWidget(QLabel("模糊強度"))
        main_layout.addWidget(self.blur_slider)
        main_layout.addWidget(self.blur_value_label)

        # 狀態欄
        self.status_label = QLabel("歡迎使用景深效果應用！")
        main_layout.addWidget(self.status_label)

        # 固定高度的進度條
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(30)
        main_layout.addWidget(self.progress_bar)

        # 圖像顯示區域
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.image_label)

        # 初始化選取狀態
        self.selecting = False
        self.start_point = None
        self.rects = []

    def generate_gif(self):
        """生成動圖的處理邏輯"""
        if self.result is None or self.focus_mask is None:
            self.status_label.setText("尚未生成景深圖像，請先完成圖像處理！")
            return

        self.status_label.setText("正在生成動圖...")
        start_time = time.time()

        # 获取影片参数
        durations = self.duration_input.value()
        fpss = self.fps_input.value()

        # 取得不帶副檔名的輸入檔案名稱
        input_file_name_without_extension = self.file_path.split("/")[-1].rsplit(".", 1)[0]
        default_file_name = f"{input_file_name_without_extension}_Short_Video_Result"

        # 檢查是否提供了有效的檔案名稱
        if not input_file_name_without_extension:
            self.status_label.setText("未提供輸入檔案名稱！")
            return

        # 彈出文件保存對話框，並選擇保存路徑
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "儲存影片", 
            default_file_name + ".mp4",  # 預設檔案名稱
            "MP4 文件 (*.mp4);;所有文件 (*)", 
            options=options
        )

        # 如果使用者取消或未選擇檔案路徑，顯示提示並退出
        if not file_path:
            self.status_label.setText("儲存取消，未選擇檔案路徑。")
            return

        # 確保選擇的檔案路徑有 .mp4 副檔名，若無則自動添加
        if not file_path.endswith('.mp4'):
            file_path += '.mp4'

        # 創建生成幀的目錄
        output_directory = "generated_frames"
        os.makedirs(output_directory, exist_ok=True)

        # 呼叫生成影片的函數
        try:
            self.generate_video(
                self.result,
                self.focus_mask,
                output_video_path=file_path,  # 使用選擇的檔案路徑
                amplitude_fg=10,
                amplitude_bg=9,
                frequency_fg=1.0,
                frequency_bg=0.95,
                duration=durations,  # 影片長度為 5 秒
                fps=fpss,  # 每秒 30 幀
                smoothing_kernel=(15, 15)
            )
        except (OSError, cv2.error, ValueError) as error:
            self.status_label.setText(f"影片生成失敗：{error}")
            return

        # 計算處理時間並顯示結果
        end_time = time.time()
        processing_time = end_time - start_time
        self.status_label.setText(f"處理完成，花費時間: {processing_time:.2f} 秒，動圖生成完成！保存到: {file_path}")

        #self.status_label.setText(f"動圖生成完成！圖像已保存到資料夾: {output_directory}")
    # 清除選取矩形
    def clear_selection(self):
        if not self.rectangles:
            self.status_label.setText("尚未選取任何區域")
        else:
            self.rectangles.clear()  # 清空矩形選取
            self.display_image_with_rects = self.display_image.copy()  # 重置顯示圖像
            self.update_image()  # 更新顯示圖像
            self.status_label.setText("已清除所有選取區域")

    def process_multiple_areas(self):
        if not self.rectangles:
            self.status_label.setText("尚未選取任何區域！")
            return

        # 確保UI更新發生在主線程
        QTimer.singleShot(0, lambda: self.status_label.setText("開始處理多區域..."))
        start_time = time.time()
        # 執行GrabCut處理
        self.result = None
        try:
            self.focus_rects, self.focus_mask = grabcut_for_multiple_areas_with_floodfill(self.image, self.rectangles)
        except (cv2.error, ValueError) as error:
            self.focus_mask = None
            self.status_label.setText(f"分割失敗，請重新框選：{error}")
            return

        if self.focus_rects:
            self.status_label.setText(f"已處理 {len(self.focus_rects)} 個區域，請繼續後續處理。")
            self.apply_depth_of_field()
            end_time = time.time()
            processing_time = end_time - start_time
            self.status_label.setText(f"處理完成，花費時間: {processing_time:.2f} 秒")
        else:
            self.status_label.setText("未能處理任何區域。")

    def process_image(self):
        if self.image is None:
            self.statusBar().showMessage("請先選擇圖像文件")
            return
        start_time = time.time()
        # 自動抓取中央焦點區域進行處理
        self.result = None
        try:
            self.focus_rect, self.focus_mask = grabcut_for_focus_area(self.image)
        except (cv2.error, ValueError) as error:
            self.focus_mask = None
            self.status_label.setText(f"分割失敗，請改用多物件框選：{error}")
            return
        if self.focus_rect is None or self.focus_mask is None:
            self.result = None
            self.status_label.setText("未找到前景，請改用多物件框選。")
            return
        
        self.statusBar().showMessage("焦點區域已選取，開始處理圖像...")
        self.status_label.setText(f"自動框選焦點範圍: {self.focus_rect}")
        self.apply_depth_of_field()
        # 記錄處理結束時間
        end_time = time.time()
        # 計算處理時間（秒）
        processing_time = end_time - start_time
        # 顯示處理時間
        self.status_label.setText(f"處理完成，花費時間: {processing_time:.2f} 秒")

    def open_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
                    self, "選擇圖像", "", "Image Files (*.jpg *.jpeg *.png);;All Files (*)", options=options
        )

        if file_path:
            self.file_path = file_path
            self.result = None
            self.focus_mask = None
            self.rectangles.clear()
            self.selecting = False
            self.start_point = None
            self.display_image_with_rects = None
            self.image_label.clear()
            try:
                # 嘗試加載圖像，處理中文路徑
                self.image = self.read_image(file_path)
                if self.image is not None:
                    self.status_label.setText("圖像加載成功！")
                    # 儲存原始圖片，並將顯示圖像初始化為原始圖像
                    self.display_image = self.image.copy()
                    self.display_image_with_rects = self.display_image.copy()  # 初始化帶矩形標註的顯示圖像
                    self.update_image()  # 更新顯示圖像
                else:
                    self.status_label.setText("無法加載圖像，請確認路徑是否正確！")
            except Exception as e:
                self.status_label.setText("讀取圖像時發生錯誤！")
        else:
            self.status_label.setText("未選擇圖像文件！")


    def read_image(self,file_path):
        """使用字節流方式讀取圖像"""
        # 確認文件存在
        if not os.path.exists(file_path):
            return None
        
        # 以 UTF-8 編碼將路徑轉換為字節流
        
        # 打開並讀取文件的字節流
        try:
            with open(file_path, 'rb') as f:
                file_bytes = np.asarray(bytearray(f.read()), dtype=np.uint8)
            
            # 使用 imdecode 來讀取圖像
            self.image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            
            if self.image is None:
                return None
            
            return self.image
        except Exception as e:
            return None

    def start_selecting_objects(self):
        """啟動選取多物件模式"""
        if self.image is None:
            self.status_label.setText("請先選擇圖像。")
            return
        self.status_label.setText("進入多物件選取模式，請在圖片上框選矩形區域。")
        self.selecting = True
        self.rects = []  # 重置之前的矩形框
        self.image_label.mousePressEvent = self.start_drawing
        self.image_label.mouseMoveEvent = self.update_drawing
        self.image_label.mouseReleaseEvent = self.end_drawing

    def image_coordinates(self, position):
        """扣除置中留白，將滑鼠位置換算至原始圖片。"""
        pixmap = self.image_label.pixmap()
        if self.image is None or pixmap is None:
            return None
        height, width = self.image.shape[:2]
        offset_x = (self.image_label.width() - pixmap.width()) / 2
        offset_y = (self.image_label.height() - pixmap.height()) / 2
        x = np.clip((position.x() - offset_x) * width / pixmap.width(), 0, width)
        y = np.clip((position.y() - offset_y) * height / pixmap.height(), 0, height)
        return float(x), float(y)

    def start_drawing(self, event):
        if self.selecting:
            # 計算顯示圖像和原始圖像之間的縮放比例
            
            # 計算鼠標在原始圖像上的位置
            self.start_point = self.image_coordinates(event.pos())

    def update_drawing(self, event):
        """更新繪製矩形"""
        if self.selecting and self.start_point:
            if not isinstance(self.display_image, np.ndarray):
                self.status_label.setText("圖像數據無效，請重新載入圖像。")
                return

            # 計算顯示圖像和原始圖像之間的縮放比例
            
            # 計算當前鼠標在原始圖像上的位置
            end_point = self.image_coordinates(event.pos())

            # 顯示即時框選的矩形
            temp_image = self.display_image.copy()
            cv2.rectangle(
                temp_image,
                (int(self.start_point[0]), int(self.start_point[1])),  # 使用原始坐標系
                (int(end_point[0]), int(end_point[1])),  # 使用終點的坐標
                (0, 255, 0),
                2
            )
            self.display_image_with_rects = temp_image  # 更新顯示的圖像
            self.update_image()  # 即時顯示更新

    def end_drawing(self, event):
        """結束繪製並記錄矩形框"""
        if not self.selecting or self.start_point is None or self.image is None:
            return
        if not hasattr(self, 'display_image_with_rects') or self.display_image_with_rects is None:
            self.display_image_with_rects = self.display_image.copy()  # 如果尚未初始化，進行初始化

        # 計算顯示圖像和原始圖像之間的縮放比例

        # 計算當前鼠標在原始圖像上的位置
        end_point = self.image_coordinates(event.pos())

        # 保存矩形信息
        x1, x2 = sorted((self.start_point[0], end_point[0]))
        y1, y2 = sorted((self.start_point[1], end_point[1]))
        self.start_point = None
        if int(x2) <= int(x1) or int(y2) <= int(y1):
            self.status_label.setText("框選範圍太小，請重新框選。")
            return
        self.rectangles.append((x1, y1, x2 - x1, y2 - y1))

        # 繪製所有矩形
        for r in self.rectangles:
            cv2.rectangle(self.display_image_with_rects, (int(r[0]), int(r[1])), 
                        (int(r[0] + r[2]), int(r[1] + r[3])), (0, 255, 0), 2)

        self.update_image()  # 更新顯示圖像


    def update_image(self):
        """將當前圖像顯示在 QLabel 中"""
        if self.image is not None:
            # 取得圖像的原始尺寸
            height, width = self.image.shape[:2]
            # 為操作列預留空間，避免原圖超出螢幕而裁掉可框選區域。
            available = QApplication.primaryScreen().availableGeometry()
            max_height = max(120, min(540, available.height() - 260))
            max_width = max(160, min(1000, available.width() - 80))
            scale = min(max_height / height, max_width / width)
            display_height = max(1, int(height * scale))
            new_width = max(1, int(width * scale))

            # 調整圖像大小
            resized_image = cv2.resize(self.image, (new_width, display_height))
            resized_image = cv2.cvtColor(resized_image, cv2.COLOR_BGR2RGB)

            # 如果有矩形框，將矩形繪製到圖像上
            if hasattr(self, 'display_image_with_rects') and self.display_image_with_rects is not None:
                resized_image_with_rects = cv2.resize(self.display_image_with_rects, (new_width, display_height))
                resized_image_with_rects = cv2.cvtColor(resized_image_with_rects, cv2.COLOR_BGR2RGB)
                image_to_display = resized_image_with_rects
            else:
                image_to_display = resized_image

            # 將圖像轉換為 QImage 並顯示
            h, w, ch = image_to_display.shape
            bytes_per_line = ch * w
            qimage = QImage(image_to_display.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)
            self.image_label.setPixmap(pixmap)

    
    def display_image(self):
            if self.image is not None:
                display_height = self.desired_display_height
                height, width = self.image.shape[:2]
                scale = display_height / height
                new_width = int(width * scale)
                resized_image = cv2.resize(self.image, (new_width, display_height))
                resized_image = cv2.cvtColor(resized_image, cv2.COLOR_BGR2RGB)

                h, w, ch = resized_image.shape
                bytes_per_line = ch * w
                qimage = QImage(resized_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qimage)
                self.image_label.setPixmap(pixmap)
    ################################
            
    def apply_depth_of_field(self): 
        if self.focus_mask is None:
            self.status_label.setText("尚未框選焦點區域！")
            return

        self.status_label.setText("開始進行景深處理...")
        #start_time = time.time()

        height, width, _ = self.image.shape
        focus_mask = self.focus_mask  # 使用分割出的焦點掩膜

        # 計算距離地圖（以圖像中心為基準）
        y, x = np.meshgrid(np.arange(height), np.arange(width), indexing='ij')
        distance_map = np.sqrt((x - width // 2) ** 2 + (y - height // 2) ** 2)

        # 調整模糊範圍
        max_blur = max(3, int(self.blur_strength * 2) | 1)
        min_blur = 1
        blur_map = np.where(focus_mask > 0, 0, np.interp(distance_map, (distance_map.min(), distance_map.max()), (min_blur, max_blur)).astype(int))

        # 構建模糊層
        blur_radii = list(range(min_blur, max_blur + 1, 2))
        self.status_label.setText("構建模糊層中...")
        blurred_layers = generate_blurred_layers(self.image, blur_radii)

        # 初始化進度條
        self.progress_bar.setMaximum(height)
        self.progress_bar.setValue(0)

        # 混合不同模糊層
        result = np.zeros_like(self.image, dtype=np.float32)
        self.status_label.setText("應用模糊層到圖像中...")

        for i in range(height):
            for j in range(width):
                if focus_mask[i, j] == 1:  # 如果是焦點區域，保持原圖像素
                    result[i, j] = self.image[i, j]
                else:  # 否則應用模糊
                    blur_index = int(np.clip((blur_map[i, j] - min_blur) // 2, 0, len(blurred_layers) - 1))
                    result[i, j] = blurred_layers[blur_index][i, j]

            # 更新進度條
            self.progress_bar.setValue(i + 1)
            QApplication.processEvents()

        self.result = result.astype(np.uint8)

        #end_time = time.time()
        #elapsed_time = end_time - start_time
        #self.status_label.setText(f"處理完成！耗時：{elapsed_time:.2f} 秒")
        #self.status_label.setText(f"處理完成！耗時：{elapsed_time:.2f} 秒")

    def save_result(self):
        if self.result is None:
            self.statusBar().showMessage("尚未生成結果圖像")
            return

        # 默認檔名為 "輸入檔_depth_field_result"
        input_file_name = "輸入檔"
        
        # 如果已經選擇了圖像檔案，從檔案路徑中提取檔名
        if hasattr(self, 'file_path') and self.file_path:
            input_file_name = self.file_path.split("/")[-1].rsplit(".", 1)[0]

        # 預設保存名稱
        default_filename = f"{input_file_name}_depth_field_result.jpg"

        # 彈出文件保存對話框，並選擇保存路徑
        save_path, _ = QFileDialog.getSaveFileName(self, "保存結果圖像", default_filename, "Image Files (*.jpg *.png *.bmp *.tiff)")
        
        if save_path:
            # 保存圖像
            extension = os.path.splitext(save_path)[1].lower() or '.jpg'
            if not os.path.splitext(save_path)[1]:
                save_path += extension
            try:
                success, encoded = cv2.imencode(extension, self.result)
                if not success:
                    raise OSError("圖像編碼失敗")
                encoded.tofile(save_path)
            except (OSError, cv2.error) as error:
                self.statusBar().showMessage(f"圖像儲存失敗：{error}")
                return
            self.statusBar().showMessage(f"結果圖像已保存到: {save_path}")
        else:
            self.statusBar().showMessage("保存操作已取消")

    def show_result_in_window(self):
        # 顯示結果的OpenCV視窗
        if self.result is None:
            self.statusBar().showMessage("請先選擇圖像文件！")
            return

        try:
            # 確保結果圖像是RGB格式
            result_rgb = cv2.cvtColor(self.result, cv2.COLOR_BGR2RGB)
            result_rgb = result_rgb[:, :, ::-1]  # 顏色通道反轉
            scale_factor = 0.3  # 你可以根据需要调整倍数
            height, width = result_rgb.shape[:2]
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            resized_image = cv2.resize(result_rgb, (new_width, new_height))
            # 顯示圖像
            cv2.imshow("Result",resized_image)#result_rgb
            cv2.waitKey(0)  # 等待按鍵按下
            cv2.destroyAllWindows()  # 關閉顯示窗口

        except Exception as e:
            # 捕捉錯誤並顯示錯誤信息
            self.statusBar().showMessage(f"顯示結果時出現錯誤: {e}")

    def update_blur_strength(self, value):
        """更新模糊強度並更新顯示的數值"""
        self.blur_strength = int(value)
        self.blur_value_label.setText(str(self.blur_strength))  # 更新數值顯示
    def generate_video(self, image, mask, output_video_path, amplitude_fg, amplitude_bg, frequency_fg, frequency_bg, duration, fps, smoothing_kernel=(15, 15)): 
        """
        生成影片並更新進度條顯示。

        參數：
            image (np.ndarray): 輸入的影像。
            mask (np.ndarray): 二進制遮罩（前景為1，背景為0）。
            output_video_path (str): 輸出視頻的路徑。
            amplitude_fg (float): 前景位移的幅度。
            amplitude_bg (float): 背景位移的幅度。
            frequency_fg (float): 前景位移的頻率。
            frequency_bg (float): 背景位移的頻率。
            duration (float): 視頻的長度（秒）。
            fps (int): 每秒幀數。
            smoothing_kernel (tuple): 高斯模糊核大小，用於平滑前後景交界處的邊緣。

        返回：
            None
        """
        height, width = image.shape[:2]
        num_frames = int(duration * fps)

        # 設置進度條的最大值
        self.progress_bar.setMaximum(num_frames)

        # 增加邊界來處理位移邊緣
        border_size = max(int(max(amplitude_fg, amplitude_bg)), 10)
        padded_image = cv2.copyMakeBorder(image, border_size, border_size, border_size, border_size, cv2.BORDER_REFLECT)
        padded_mask = cv2.copyMakeBorder(mask, border_size, border_size, border_size, border_size, cv2.BORDER_CONSTANT, value=0)

        padded_height, padded_width = padded_image.shape[:2]

        # 定義視頻編碼器並創建 VideoWriter 物件
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # 使用適合 MP4 容器的編碼
        #fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # MP4 格式編碼
        #fourcc = cv2.VideoWriter_fourcc(*'avc1')  # MP4 格式編碼
        video_writer = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))
        if not video_writer.isOpened():
            video_writer.release()
            raise OSError("無法開啟影片輸出，請確認路徑與編碼支援。")

        # 創建坐標網格
        y_coords, x_coords = np.meshgrid(np.arange(padded_height), np.arange(padded_width), indexing='ij')

        try:
            for frame_idx in range(num_frames):
                t = frame_idx / fps
    
                # 計算前景和背景的位移
                displacement_fg = amplitude_fg * np.sin(2 * np.pi * frequency_fg * t)
                displacement_bg = amplitude_bg * np.sin(2 * np.pi * frequency_bg * t)
    
                # 前景位移
                fg_y = np.clip(y_coords + displacement_fg, 0, padded_height - 1).astype(np.int32)
                fg_x = np.clip(x_coords + displacement_fg, 0, padded_width - 1).astype(np.int32)
    
                # 背景位移
                bg_y = np.clip(y_coords + displacement_bg, 0, padded_height - 1).astype(np.int32)
                bg_x = np.clip(x_coords + displacement_bg, 0, padded_width - 1).astype(np.int32)
    
                # 分離前景和背景
                foreground = np.zeros_like(padded_image)
                background = np.zeros_like(padded_image)
                for c in range(padded_image.shape[2]):  # 遍歷每個顏色通道
                    foreground[..., c] = padded_image[fg_y, fg_x, c] * padded_mask
                    background[..., c] = padded_image[bg_y, bg_x, c] * (1 - padded_mask)
    
                # 混合前景和背景，避免黑邊
                alpha = padded_mask.astype(np.float32)
                alpha = np.clip(alpha, 0.0, 1.0)
                smoothed_image = foreground * alpha[..., None] + background * (1 - alpha[..., None])
    
                # 裁剪回原始大小
                cropped_image = smoothed_image[border_size:-border_size, border_size:-border_size].astype(np.uint8)
    
                # 寫入當前幀到視頻
                video_writer.write(cropped_image)
    
                # 更新進度條
                self.progress_bar.setValue(frame_idx + 1)
    
        finally:
            video_writer.release()

        # 釋放視頻寫入物件
        if not os.path.isfile(output_video_path) or os.path.getsize(output_video_path) == 0:
            raise OSError("影片輸出檔案不存在或為空。")
        self.status_label.setText("影片生成完成！")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = DepthOfFieldApp()
    ex.show()
    sys.exit(app.exec_())
