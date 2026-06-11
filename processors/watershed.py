import cv2
import numpy as np

from .morphology import _kernel


def watershed(img, params, **kwargs):
    if len(img.shape) == 2:
        color = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        binary = img
    else:
        color = img.copy()
        binary = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(
            binary, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

    kernel = _kernel(params)
    opening_iterations = int(params.get("opening_iterations", 2))
    opening_img = cv2.morphologyEx(
        binary, cv2.MORPH_OPEN, kernel, iterations=opening_iterations
    )
    dilation_iterations = int(params.get("dilation_iterations", 3))
    sure_bg = cv2.dilate(opening_img, kernel, iterations=dilation_iterations)
    distance_transform = int(params.get("distance_transform", 5))
    dist = cv2.distanceTransform(opening_img, cv2.DIST_L2, distance_transform)
    _, sure_fg = cv2.threshold(dist, 0.5 * dist.max(), 255, 0)
    sure_fg = np.uint8(sure_fg)
    unknown = cv2.subtract(sure_bg, sure_fg)
    _, markers = cv2.connectedComponents(sure_fg)
    markers = markers + 1
    markers[unknown == 255] = 0
    markers = cv2.watershed(color, markers)

    out = color.copy()

    if kwargs.get("islast", False):
        # 最終的な出力では、輪郭を赤色で描画
        out[markers == -1] = [0, 0, 255]
    else:
        # 最後ではない場合は、太い黒線で輪郭を描画
        boundary = np.uint8(markers == -1) * 255
        kernel = np.ones((3, 3), np.uint8)  # 3x3
        boundary = cv2.dilate(boundary, kernel, iterations=1)
        out[boundary > 0] = [0, 0, 0]

    return out
