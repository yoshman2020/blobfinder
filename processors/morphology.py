import cv2
import numpy as np

from .registry import register


def _kernel(params):
    k = int(params.get("kernel", 3))
    return np.ones((k, k), np.uint8)


def ensure_binary(img):
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, b = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
    return b


@register("opening")
def opening(img, params, **kwargs):
    return cv2.morphologyEx(img, cv2.MORPH_OPEN, _kernel(params))


@register("closing")
def closing(img, params, **kwargs):
    return cv2.morphologyEx(img, cv2.MORPH_CLOSE, _kernel(params))


@register("dilate")
def dilate(img, params, **kwargs):
    itr = int(params.get("iterations", 1))
    return cv2.dilate(img, _kernel(params), iterations=itr)


@register("erode")
def erode(img, params, **kwargs):
    itr = int(params.get("iterations", 1))
    return cv2.erode(img, _kernel(params), iterations=itr)


@register("morphology")
def morphology_gradient(img, params, **kwargs):
    return cv2.morphologyEx(img, cv2.MORPH_GRADIENT, _kernel(params))


@register("top_hat")
def top_hat(img, params, **kwargs):
    return cv2.morphologyEx(img, cv2.MORPH_TOPHAT, _kernel(params))


@register("black_hat")
def black_hat(img, params, **kwargs):
    return cv2.morphologyEx(img, cv2.MORPH_BLACKHAT, _kernel(params))


def binary_fill_holes(binary):
    # binary: 0/255 の2値画像
    flood = binary.copy()

    h, w = binary.shape[:2]
    mask = np.zeros((h + 2, w + 2), np.uint8)

    # 背景を塗りつぶす
    cv2.floodFill(flood, mask, (0, 0), 255)  # type: ignore

    # 背景を反転
    flood_inv = cv2.bitwise_not(flood)

    # 元画像と合成すると穴が埋まる
    return cv2.bitwise_or(binary, flood_inv)


@register("fill_holes")
def fill_holes(img, params, **kwargs):
    b = ensure_binary(img)
    filled = binary_fill_holes(b)
    return filled


@register("remove_border")
def remove_border_blobs(img, params, **kwargs):
    b = ensure_binary(img)
    h, w = b.shape
    mask = np.zeros((h + 2, w + 2), np.uint8)
    flood = b.copy()
    for x in range(w):
        if flood[0, x] == 255:
            cv2.floodFill(flood, mask, (x, 0), 0)  # type: ignore
        if flood[h - 1, x] == 255:
            cv2.floodFill(flood, mask, (x, h - 1), 0)  # type: ignore
    for y in range(h):
        if flood[y, 0] == 255:
            cv2.floodFill(flood, mask, (0, y), 0)  # type: ignore
        if flood[y, w - 1] == 255:
            cv2.floodFill(flood, mask, (w - 1, y), 0)  # type: ignore
    return flood
