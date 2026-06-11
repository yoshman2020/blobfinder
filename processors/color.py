import cv2
import numpy as np


def extract_r(img, params, **kwargs):
    out = np.zeros_like(img)
    out[:, :, 2] = img[:, :, 2]
    return out


def extract_g(img, params, **kwargs):
    out = np.zeros_like(img)
    out[:, :, 1] = img[:, :, 1]
    return out


def extract_b(img, params, **kwargs):
    out = np.zeros_like(img)
    out[:, :, 0] = img[:, :, 0]
    return out


def gray(img, params, **kwargs):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def h_channel(img, params, **kwargs):

    hls = cv2.cvtColor(img, cv2.COLOR_BGR2HLS)

    return hls[:, :, 0]


def l_channel(img, params, **kwargs):

    hls = cv2.cvtColor(img, cv2.COLOR_BGR2HLS)

    return hls[:, :, 1]


def s_channel(img, params, **kwargs):

    hls = cv2.cvtColor(img, cv2.COLOR_BGR2HLS)

    return hls[:, :, 2]


def invert(img, params, **kwargs):
    if len(img.shape) == 3:
        out = np.zeros_like(img)
        out[:, :, 0] = cv2.bitwise_not(img[:, :, 0])
        out[:, :, 1] = cv2.bitwise_not(img[:, :, 1])
        out[:, :, 2] = cv2.bitwise_not(img[:, :, 2])
        return out
    return cv2.bitwise_not(img)
