import cv2
import numpy as np

from .image_utils import ensure_bgr, ensure_uint8
from .registry import register


@register("r")
def extract_r(img, params, **kwargs):
    img = ensure_uint8(img)
    out = np.zeros_like(img)
    out[:, :, 2] = img[:, :, 2]
    return out


@register("g")
def extract_g(img, params, **kwargs):
    img = ensure_uint8(img)
    out = np.zeros_like(img)
    out[:, :, 1] = img[:, :, 1]
    return out


@register("b")
def extract_b(img, params, **kwargs):
    img = ensure_uint8(img)
    out = np.zeros_like(img)
    out[:, :, 0] = img[:, :, 0]
    return out


@register("gray")
def gray(img, params, **kwargs):
    img = ensure_bgr(img)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


@register("h")
def h_channel(img, params, **kwargs):
    img = ensure_bgr(img)
    img = ensure_uint8(img)
    hls = cv2.cvtColor(img, cv2.COLOR_BGR2HLS)
    return hls[:, :, 0]


@register("l")
def l_channel(img, params, **kwargs):
    img = ensure_bgr(img)
    img = ensure_uint8(img)
    hls = cv2.cvtColor(img, cv2.COLOR_BGR2HLS)
    return hls[:, :, 1]


@register("s")
def s_channel(img, params, **kwargs):
    img = ensure_bgr(img)
    img = ensure_uint8(img)
    hls = cv2.cvtColor(img, cv2.COLOR_BGR2HLS)
    return hls[:, :, 2]


@register("invert")
def invert(img, params, **kwargs):
    img = ensure_uint8(img)
    if len(img.shape) == 3:
        out = np.zeros_like(img)
        out[:, :, 0] = cv2.bitwise_not(img[:, :, 0])
        out[:, :, 1] = cv2.bitwise_not(img[:, :, 1])
        out[:, :, 2] = cv2.bitwise_not(img[:, :, 2])
        return out
    return cv2.bitwise_not(img)


@register("resize")
def resize(img, params, **kwargs):
    w = int(params.get("width", 0))
    h = int(params.get("height", 0))
    scale = float(params.get("scale", 1.0))
    if w > 0 and h > 0:
        return cv2.resize(img, (w, h))
    if w > 0:
        h = int(img.shape[0] * w / img.shape[1])
        return cv2.resize(img, (w, h))
    if h > 0:
        w = int(img.shape[1] * h / img.shape[0])
        return cv2.resize(img, (w, h))
    if scale != 1.0:
        return cv2.resize(img, None, fx=scale, fy=scale)
    return img
