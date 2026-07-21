import cv2
import numpy as np

from .image_utils import ensure_binary
from .morphology_utils import _kernel
from .registry import register


@register("opening")
def opening(img, params, **kwargs):
    img = ensure_binary(img)
    return cv2.morphologyEx(img, cv2.MORPH_OPEN, _kernel(params))


@register("closing")
def closing(img, params, **kwargs):
    img = ensure_binary(img)
    return cv2.morphologyEx(img, cv2.MORPH_CLOSE, _kernel(params))


@register("dilate")
def dilate(img, params, **kwargs):
    img = ensure_binary(img)
    itr = int(params.get("iterations", 1))
    return cv2.dilate(img, _kernel(params), iterations=itr)


@register("erode")
def erode(img, params, **kwargs):
    img = ensure_binary(img)
    itr = int(params.get("iterations", 1))
    return cv2.erode(img, _kernel(params), iterations=itr)


@register("morphology")
def morphology_gradient(img, params, **kwargs):
    img = ensure_binary(img)
    return cv2.morphologyEx(img, cv2.MORPH_GRADIENT, _kernel(params))


@register("top_hat")
def top_hat(img, params, **kwargs):
    img = ensure_binary(img)
    return cv2.morphologyEx(img, cv2.MORPH_TOPHAT, _kernel(params))


@register("black_hat")
def black_hat(img, params, **kwargs):
    img = ensure_binary(img)
    return cv2.morphologyEx(img, cv2.MORPH_BLACKHAT, _kernel(params))


@register("fill_holes")
def fill_holes(img, params, **kwargs):
    img = ensure_binary(img)
    flood = img.copy()
    h, w = img.shape[:2]
    mask = np.zeros((h + 2, w + 2), np.uint8)
    # 外側から黒を白に塗り潰す（背景を白にする）
    cv2.floodFill(flood, mask, (0, 0), 255)  # type: ignore

    # flood の黒い領域 = 穴（背景から繋がってない黒）
    # これを白にして元画像に足す
    flood_inv = cv2.bitwise_not(flood)  # 穴だけ（白）、その他黒
    filled = cv2.bitwise_or(img, flood_inv)
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
