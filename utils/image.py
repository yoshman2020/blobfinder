from pathlib import Path

import cv2
import numpy as np


def imread_safe(path: str):
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def save_image_as_png(
    image,
    image_id: str,
    i: int | None,
    out_dir: Path,
):
    path = (
        out_dir / f"{image_id}.png"
        if i is None
        else out_dir / f"{image_id}_step_{i}.png"
    )

    tmp = image

    if tmp.dtype != np.uint8:
        tmp = np.nan_to_num(
            tmp,
            nan=0.0,
            posinf=255.0,
            neginf=0.0,
        )
        tmp = np.clip(tmp, 0, 255).astype(np.uint8)

    if len(tmp.shape) == 2:
        tmp = cv2.cvtColor(tmp, cv2.COLOR_GRAY2BGR)

    cv2.imwrite(str(path), tmp)
