import numpy as np


def _kernel(params):
    """形態学処理用カーネル生成"""
    k = int(params.get("kernel", 3))
    if k % 2 == 0:
        k += 1
    return np.ones((k, k), np.uint8)
