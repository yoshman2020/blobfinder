import cv2
import numpy as np


def ensure_gray(img):
    """1チャンネルのグレースケールに統一"""
    if len(img.shape) == 2:
        return img
    elif img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    elif img.shape[2] == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    return img


def ensure_uint8(img):
    """uint8データ型に統一"""
    if img.dtype == np.uint8:
        return img
    elif img.dtype in (np.float32, np.float64):
        return np.clip(img, 0, 255).astype(np.uint8)
    else:
        return img.astype(np.uint8)


def ensure_bgr(img):
    """BGR 3チャンネルに統一"""
    if len(img.shape) == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif len(img.shape) == 3 and img.shape[2] == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img


def ensure_binary(img):
    """バイナリ画像に統一"""
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img = ensure_uint8(img)
    _, b = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
    return b
