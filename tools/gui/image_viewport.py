"""RAW10 image display widget."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

_TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(_TOOLS_DIR / "lib") not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR / "lib"))

from raw10 import decode_raw10  # noqa: E402


class ImageViewport(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw_data: Optional[bytes] = None
        self._raw16: Optional[np.ndarray] = None
        self._rgb: Optional[np.ndarray] = None
        self._width = 0
        self._height = 0
        self._elapsed_s = 0.0

        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        self.btn_save_png = QPushButton("保存 PNG")
        self.btn_save_raw = QPushButton("保存 RAW")
        self.btn_save_png.setEnabled(False)
        self.btn_save_raw.setEnabled(False)
        btn_row.addWidget(self.btn_save_png)
        btn_row.addWidget(self.btn_save_raw)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.label = QLabel("等待图像...")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setMinimumSize(640, 480)
        layout.addWidget(self.label, stretch=1)

        self.info_label = QLabel("")
        layout.addWidget(self.info_label)

    def display_raw10(self, data: bytes, width: int = 640, height: int = 480,
                      elapsed_s: float = 0.0) -> None:
        self._raw_data = data
        self._width = width
        self._height = height
        self._elapsed_s = elapsed_s

        try:
            raw16 = decode_raw10(data, width, height)
            raw8 = (raw16 >> 2).astype(np.uint8)

            # Bayer 相位: 实测 RG 会把黄/青对调(R/B 反), 用 BG 修正。
            try:
                color = cv2.cvtColor(raw8, cv2.COLOR_BayerBG2RGB)
            except Exception:
                color = cv2.cvtColor(raw8, cv2.COLOR_GRAY2RGB)

            self._raw16 = raw16
            self._rgb = color.copy()

            h, w, ch = color.shape
            qimg = QImage(color.data, w, h, w * ch, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg.copy())
            self.label.setPixmap(pixmap.scaled(
                self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

            mean_val = float(np.mean(raw16))
            self.info_label.setText(
                f"分辨率: {w}×{h} | 像素均值: {mean_val:.1f} | "
                f"数据量: {len(data)} B | 耗时: {elapsed_s:.1f}s")
            self.btn_save_png.setEnabled(True)
            self.btn_save_raw.setEnabled(True)
        except Exception as e:
            self._raw16 = None
            self._rgb = None
            self.btn_save_png.setEnabled(False)
            self.btn_save_raw.setEnabled(False)
            self.label.setText(f"解码失败: {e}")

    def save_png(self, path: str) -> bool:
        if self._rgb is None:
            return False
        bgr = cv2.cvtColor(self._rgb, cv2.COLOR_RGB2BGR)
        return bool(cv2.imwrite(path, bgr))

    def save_raw(self, path: str) -> bool:
        if self._raw_data is None:
            return False
        Path(path).write_bytes(self._raw_data)
        return True

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._rgb is not None:
            h, w, ch = self._rgb.shape
            qimg = QImage(self._rgb.data, w, h, w * ch, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg.copy())
            self.label.setPixmap(pixmap.scaled(
                self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
