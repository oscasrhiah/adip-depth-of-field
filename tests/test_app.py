import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np
from PyQt5.QtCore import QPoint
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication

import Depth_of_field as app


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = app.DepthOfFieldApp()
        self.image = np.full((48, 64, 3), (30, 130, 30), dtype=np.uint8)
        self.image[15:34, 24:41] = (20, 20, 230)

    def tearDown(self):
        self.window.close()

    def test_central_segmentation_and_depth(self):
        rect, mask = app.grabcut_for_focus_area(self.image)
        self.assertIsNotNone(rect, "合成中央主體應可分割")
        self.assertGreater(mask.sum(), 0)
        self.window.image = self.image.copy()
        self.window.focus_mask = mask
        self.window.blur_strength = 3
        self.window.apply_depth_of_field()
        np.testing.assert_array_equal(self.window.result[mask == 1], self.image[mask == 1])
        self.assertEqual(self.window.result.shape, self.image.shape)

    def test_multiple_roi_segmentation(self):
        self.image[15:34, 45:56] = (230, 20, 20)
        rects, mask = app.grabcut_for_multiple_areas_with_floodfill(
            self.image, [(20, 10, 24, 29), (42, 10, 18, 29)]
        )
        self.assertEqual(len(rects), 2, "兩個獨立主體均應有前景")
        self.assertEqual(mask[24, 30], 1)
        self.assertEqual(mask[24, 50], 1)
        self.assertEqual(mask[0, 0], 0)

    def test_empty_foreground_has_status_instead_of_exception(self):
        self.window.image = self.image.copy()
        self.window.result = self.image.copy()
        with patch.object(app.cv2, "grabCut"):
            self.window.process_image()
        self.assertIsNone(self.window.result)
        self.assertIn("未找到前景", self.window.status_label.text())

    def test_unicode_image_read_save_and_reload_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "中文輸入.png"
            output_path = Path(directory) / "中文輸出.png"
            cv2.imencode(".png", self.image)[1].tofile(input_path)
            np.testing.assert_array_equal(self.window.read_image(str(input_path)), self.image)
            self.window.result = self.image.copy()
            with patch.object(app.QFileDialog, "getSaveFileName", return_value=(str(output_path), "")):
                self.window.save_result()
            self.assertTrue(output_path.is_file(), "中文路徑應能儲存圖片")
            self.window.focus_mask = np.ones((48, 64), dtype=np.uint8)
            self.window.rectangles = [(1, 1, 3, 3)]
            with patch.object(app.QFileDialog, "getOpenFileName", return_value=(str(input_path), "")):
                self.window.open_file()
            self.assertIsNone(self.window.result, "重新載入應清除舊結果")
            self.assertIsNone(self.window.focus_mask)
            self.assertEqual(self.window.rectangles, [])

    def test_failed_reload_does_not_keep_previous_output(self):
        self.window.image = self.image.copy()
        self.window.result = self.image.copy()
        self.window.focus_mask = np.ones((48, 64), dtype=np.uint8)
        with patch.object(app.QFileDialog, "getOpenFileName", return_value=("missing.png", "")):
            self.window.open_file()
        self.assertIsNone(self.window.image)
        self.assertIsNone(self.window.result, "讀取失敗也不可保留上一張結果")
        self.assertIsNone(self.window.focus_mask)

    def test_qt_platform_starts_in_project_path(self):
        result = subprocess.run(
            [sys.executable, "-c", "import Depth_of_field; from PyQt5.QtWidgets import QApplication; a=QApplication([]); print('QT_OK')"],
            cwd=Path(app.__file__).parent, capture_output=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertIn(b"QT_OK", result.stdout)

    def test_preview_fits_screen_and_keeps_aspect_ratio(self):
        self.window.image = np.zeros((200, 1000, 3), dtype=np.uint8)
        self.window.display_image_with_rects = self.window.image.copy()
        self.window.update_image()
        pixmap = self.window.image_label.pixmap()
        screen = self.qt.primaryScreen().availableGeometry()
        self.assertLessEqual(pixmap.width(), screen.width())
        self.assertLessEqual(pixmap.height(), screen.height())
        self.assertAlmostEqual(pixmap.width() / pixmap.height(), 5, delta=0.05)

    def test_segmentation_error_is_reported(self):
        self.window.image = self.image.copy()
        with patch.object(app.cv2, "grabCut", side_effect=cv2.error("無效框選")):
            self.window.process_image()
        self.assertIsNone(self.window.result)
        self.assertIn("分割失敗", self.window.status_label.text())

    def test_centered_preview_and_reverse_drag(self):
        self.window.image = self.image.copy()
        self.window.display_image = self.image.copy()
        self.window.display_image_with_rects = self.image.copy()
        self.window.image_label.setFixedSize(200, 160)
        self.window.image_label.setPixmap(QPixmap(128, 96))
        self.window.selecting = True
        # 預覽置中留白為 (36, 32)，拖曳方向由右下往左上。
        event = lambda x, y: SimpleNamespace(pos=lambda: QPoint(x, y))
        self.window.start_drawing(event(116, 92))
        self.window.end_drawing(event(56, 52))
        np.testing.assert_allclose(self.window.rectangles[0], (10, 10, 30, 20))

    def test_mp4_roundtrip_and_invalid_output(self):
        mask = np.zeros((48, 64), dtype=np.uint8)
        mask[15:34, 24:41] = 1
        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / "中文影片.mp4")
            self.window.generate_video(self.image, mask, output, 2, 1, 1, .95, 1, 4)
            capture = cv2.VideoCapture(output)
            try:
                self.assertTrue(capture.isOpened(), "輸出影片應可解碼")
                count = 0
                while True:
                    success, frame = capture.read()
                    if not success:
                        break
                    self.assertEqual(frame.shape, self.image.shape)
                    count += 1
                self.assertEqual(count, 4, "應寫出指定長度的所有影格")
            finally:
                capture.release()
            with self.assertRaises(OSError):
                self.window.generate_video(self.image, mask, str(Path(directory) / "不存在" / "demo.mp4"), 2, 1, 1, .95, 1, 4)


if __name__ == "__main__":
    unittest.main()
