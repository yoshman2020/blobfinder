import cv2
import numpy as np


def blob_analysis(img, params, **kwargs):
    """
    詳細ブロブ解析

    Parameters:
    img (numpy.ndarray): Input image.
    params (dict): Dictionary containing parameters for blob detection.
        - filter_area (bool): Whether to filter by area.
        - min_area (float): Minimum area of blobs to be considered.
        - max_area (float): Maximum area of blobs to be considered.
        - filter_circularity (bool): Whether to filter by circularity.
        - min_circularity (float): Minimum circularity of blobs to be considered.
        - filter_convexity (bool): Whether to filter by convexity.
        - min_convexity (float): Minimum convexity of blobs to be considered.
        - filter_inertia (bool): Whether to filter by inertia.
        - min_inertia (float): Minimum inertia ratio of blobs to be considered.
        - filter_color (bool): Whether to filter by color.
        - blob_color (int): Color of blobs to be considered (0 for dark, 255 for light).
        - filter_side (bool): Whether to filter by side length.
        - min_long_side (float): Minimum length of the longest side of blobs to be considered.
        - max_short_side (float): Maximum length of the shortest side of blobs to be considered.
        - filter_angle (bool): Whether to filter by angle.
        - min_angle (float): Minimum angle of blobs to be considered.
        - max_angle (float): Maximum angle of blobs to be considered.
    **kwargs: Additional keyword arguments.

    Returns:
    numpy.ndarray: Image with detected blobs and their keypoints.
    """
    # --- grayscale & binary ---
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        vis = img.copy()
    else:
        gray = img
        vis = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # --- contours ---
    contours, _ = cv2.findContours(
        binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    min_area = float(params.get("min_area", 0))
    max_area = float(params.get("max_area", 1e9))
    min_circularity = float(params.get("min_circularity", 0))
    min_convexity = float(params.get("min_convexity", 0))
    min_inertia = float(params.get("min_inertia", 0))
    blob_color = int(params.get("blob_color", 0))
    min_long_side = float(params.get("min_long_side", 0))
    max_short_side = float(params.get("max_short_side", 1e9))
    min_angle = float(params.get("min_angle", -180))
    max_angle = float(params.get("max_angle", 180))

    results = []

    for i, cnt in enumerate(contours):

        area = cv2.contourArea(cnt)
        if params.get("filter_area", False) and (
            area < min_area or area > max_area
        ):
            continue

        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue
        circularity = 4.0 * np.pi * area / (perimeter * perimeter)
        if (
            params.get("filter_circularity", False)
            and circularity < min_circularity
        ):
            continue

        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        if hull_area == 0:
            continue
        convexity = area / hull_area
        if params.get("filter_convexity", False) and convexity < min_convexity:
            continue

        # --- centroid ---
        M = cv2.moments(cnt)
        if M["m00"] == 0:
            continue

        mu20 = M["mu20"] / M["m00"]
        mu02 = M["mu02"] / M["m00"]
        mu11 = M["mu11"] / M["m00"]

        common = np.sqrt(4 * mu11 * mu11 + (mu20 - mu02) ** 2)

        lambda1 = (mu20 + mu02 + common) / 2
        lambda2 = (mu20 + mu02 - common) / 2

        if lambda1 > 0:
            inertia_ratio = lambda2 / lambda1
        else:
            inertia_ratio = 0

        if params.get("filter_inertia", False) and inertia_ratio < min_inertia:
            continue

        mask = np.zeros(gray.shape, np.uint8)
        cv2.drawContours(mask, [cnt], -1, 255, -1)

        mean_value = cv2.mean(gray, mask=mask)[0]

        if params.get("filter_color", False):
            if blob_color == 0:
                # 黒ブロブ
                if mean_value > 127:
                    continue
            else:
                # 白ブロブ
                if mean_value <= 127:
                    continue

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])

        if params.get("filter_centroid", False):
            min_cx = float(params.get("min_cx", 0))
            max_cx = float(params.get("max_cx", 1e9))
            min_cy = float(params.get("min_cy", 0))
            max_cy = float(params.get("max_cy", 1e9))
            if not (min_cx <= cx <= max_cx and min_cy <= cy <= max_cy):
                continue

        # --- rotated rectangle ---
        rect = cv2.minAreaRect(cnt)
        (rx, ry), (w, h), angle = rect

        long_side = max(w, h)
        short_side = min(w, h)

        if params.get("filter_side", False) and (
            long_side < min_long_side or short_side > max_short_side
        ):
            continue

        if params.get("filter_angle", False) and (
            angle < min_angle or angle > max_angle
        ):
            continue

        # --- axis-aligned bbox ---
        x, y, bw, bh = cv2.boundingRect(cnt)

        # --- draw ---
        box = cv2.boxPoints(rect)
        box = np.int32(box)

        cv2.drawContours(vis, [cnt], -1, (0, 255, 0), 1)
        cv2.drawContours(vis, [box], 0, (0, 0, 255), 2)

        cv2.circle(vis, (cx, cy), 3, (255, 0, 0), -1)

        cv2.putText(
            vis,
            f"{i+1}",
            (cx + 5, cy),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 0),
            1,
        )

        results.append(
            {
                "id": i + 1,
                "cx": float(cx),
                "cy": float(cy),
                "area": round(float(area), 2),
                "perimeter": round(float(perimeter), 2),
                "circularity": round(float(circularity), 4),
                "convexity": round(float(convexity), 4),
                "inertia_ratio": round(float(inertia_ratio), 4),
                "rect_long": round(float(long_side), 2),
                "rect_short": round(float(short_side), 2),
                "color": [0, 255, 0],
            }
        )

    return vis, results
