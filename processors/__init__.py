from .blob import *
from .color import *
from .filter import *
from .morphology import *
from .watershed import *

PROCESSORS = {
    "r": extract_r,
    "g": extract_g,
    "b": extract_b,
    "gray": gray,
    "h": h_channel,
    "l": l_channel,
    "s": s_channel,
    "invert": invert,
    "resize": resize,
    "equalize": histogram_equalization,
    "clahe": clahe,
    "gaussian": gaussian,
    "median": median,
    "bilateral": bilateral,
    "threshold": threshold,
    "adaptive_threshold": adaptive_threshold,
    "opening": opening,
    "closing": closing,
    "dilate": dilate,
    "erode": erode,
    "morphology": morphology_gradient,
    "top_hat": top_hat,
    "black_hat": black_hat,
    "sobel": sobel,
    "laplacian": laplacian,
    "scharr": scharr,
    "canny": canny,
    "fill_holes": fill_holes,
    "remove_border": remove_border_blobs,
    "watershed": watershed,
    "blob": blob_analysis,
}


def apply_pipeline(image, pipeline):
    current = image
    blobs = None
    for step in pipeline:
        name = step.type
        if name not in PROCESSORS:
            raise ValueError(f"unknown process: {name}")
        try:
            result = PROCESSORS[name](
                current, step.params, islast=step == pipeline[-1]
            )
        except Exception as e:
            raise RuntimeError(f"{name} failed: {e}")
        if isinstance(result, tuple):
            current, blobs = result
        else:
            current = result
            blobs = None
    return current, blobs
