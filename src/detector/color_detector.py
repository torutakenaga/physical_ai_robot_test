"""HSV による色付き箱の検出(ROS 非依存の純関数)。"""
from dataclasses import dataclass
import cv2
import numpy as np

# OpenCV の H は 0-179。赤は 0 付近と 180 付近に分かれる。
HSV_RANGES = {
    "red": [((0, 120, 30), (10, 255, 255)), ((170, 120, 30), (179, 255, 255))],
    "blue": [((100, 120, 30), (130, 255, 255))],
}
MIN_AREA_PX = 20


@dataclass
class Detection:
    found: bool
    offset: float = 0.0   # 画像中心からの水平ずれ。-1(左端)〜+1(右端)
    width_px: int = 0     # 箱の幅(近いほど大きい)
    cx: int = 0
    height_px: int = 0    # 箱の高さ(画像端で切れず、見る角度にも依存しない距離の指標)


def detect(image_rgb: np.ndarray, color: str = "red") -> Detection:
    hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
    mask = np.zeros(hsv.shape[:2], np.uint8)
    for lo, hi in HSV_RANGES[color]:
        mask |= cv2.inRange(hsv, np.array(lo), np.array(hi))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return Detection(False)
    c = max(contours, key=cv2.contourArea)
    if cv2.contourArea(c) < MIN_AREA_PX:
        return Detection(False)
    x, _, w, h = cv2.boundingRect(c)
    cx = x + w // 2
    half = image_rgb.shape[1] / 2
    return Detection(True, (cx - half) / half, w, cx, h)
