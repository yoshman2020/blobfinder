import cv2

from .morphology import _kernel
from .registry import register


def ensure_gray(img):

    if len(img.shape) == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    return img


@register("equalize")
def histogram_equalization(img, params, **kwargs):
    img = ensure_gray(img)

    return cv2.equalizeHist(img)


@register("clahe")
def clahe(img, params, **kwargs):
    img = ensure_gray(img)

    clip = params.get("clip_limit", 2.0)

    tile = params.get("tile", 8)

    clahe_filter = cv2.createCLAHE(clipLimit=clip, tileGridSize=(tile, tile))

    return clahe_filter.apply(img)


@register("gaussian")
def gaussian(img, params, **kwargs):

    kernel = params.get("kernel", 5)

    if kernel % 2 == 0:
        kernel += 1

    return cv2.GaussianBlur(img, (kernel, kernel), 0)


@register("median")
def median(img, params, **kwargs):

    kernel = params.get("kernel", 5)

    if kernel % 2 == 0:
        kernel += 1

    return cv2.medianBlur(img, kernel)


@register("bilateral")
def bilateral(img, params, **kwargs):

    kernel = params.get("kernel", 5)

    if kernel % 2 == 0:
        kernel += 1

    return cv2.bilateralFilter(img, kernel, 75, 75)


@register("threshold")
def threshold(img, params, **kwargs):
    img = ensure_gray(img)

    value = params.get("value", 127)

    _, th = cv2.threshold(img, value, 255, cv2.THRESH_BINARY)

    return th


@register("adaptive_threshold")
def adaptive_threshold(img, params, **kwargs):
    img = ensure_gray(img)

    otsu = params.get("otsu", False)
    if otsu:
        _, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return img

    block = params.get("block", 11)

    c = params.get("c", 2)

    if block % 2 == 0:
        block += 1

    return cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, c
    )

@register("sobel")
def sobel(img, params, **kwargs):
    x = int(params.get("x", True))
    y = int(params.get("y", True))
    return cv2.Sobel(img, cv2.CV_64F, x, y, _kernel(params))

@register("laplacian")
def laplacian(img, params, **kwargs):
    return cv2.Laplacian(img, cv2.CV_64F, _kernel(params))

@register("scharr")
def scharr(img, params, **kwargs):
    direction = params.get("direction", "x")
    x = 1 if direction == "x" else 0
    y = 1 if direction == "y" else 0
    return cv2.Scharr(img, cv2.CV_64F, x, y)

@register("canny")
def canny(img, params, **kwargs):
    low = params.get("low", 100)
    high = params.get("high", 200)
    return cv2.Canny(img, low, high)
