"""Recover a clean background photo and the brand marks from the nesoly carousel slides.

All slides share the same photo; each one hides a different part of it under its
text boxes. Combining the uncovered parts gives the photo without any text, and
the few areas covered on every slide (top header, bottom logo) are inpainted.
"""
import os

import cv2
import numpy as np
from PIL import Image

CROP = 12  # light screenshot border on the top and left edges

# Overlay rectangles per slide (x0, y0, x1, y1), in original slide coordinates.
ARROW = (972, 612, 1080, 738)
HEADER = (430, 66, 665, 140)
LOGO = (440, 1236, 640, 1350)
OVERLAYS = {
    "slide1.jpg": [(110, 552, 982, 800)],
    "slide2.jpg": [(48, 198, 502, 384), (595, 198, 1047, 384), (48, 538, 502, 724),
                   (595, 538, 1047, 724), (48, 908, 502, 1094), (595, 908, 1047, 1094)],
    "slide3.jpg": [(313, 376, 767, 562), (170, 724, 1004, 892), ARROW],
    "slide4.jpg": [(318, 393, 772, 579), (50, 724, 1040, 966), ARROW],
    "slide5.jpg": [(313, 383, 767, 567), (65, 724, 1025, 966), ARROW],
}


def load(src_dir, name):
    return np.asarray(Image.open(os.path.join(src_dir, name)).convert("RGB"), np.float32)


def clean_background(src_dir):
    slides = {n: load(src_dir, n) for n in OVERLAYS}
    h, w = next(iter(slides.values())).shape[:2]
    acc = np.zeros((h, w, 3), np.float32)
    cnt = np.zeros((h, w), np.float32)
    for name, img in slides.items():
        m = np.ones((h, w), np.float32)
        for x0, y0, x1, y1 in OVERLAYS[name] + [HEADER, LOGO]:
            m[max(y0 - 6, 0):y1 + 6, max(x0 - 6, 0):x1 + 6] = 0
        m[:CROP + 2] = 0
        m[:, :CROP + 2] = 0
        acc += img * m[..., None]
        cnt += m
    bg = acc / np.maximum(cnt, 1)[..., None]
    hole = (cnt == 0).astype(np.uint8)
    # Inpaint whatever is hidden on every slide, then soften it to match the blurry photo.
    filled = cv2.inpaint(np.clip(bg, 0, 255).astype(np.uint8), hole * 255, 25, cv2.INPAINT_TELEA)
    filled = filled.astype(np.float32)
    soft = cv2.GaussianBlur(filled, (0, 0), 18)
    k = cv2.GaussianBlur(hole.astype(np.float32), (0, 0), 10)[..., None]
    k = np.clip(k * 1.6, 0, 1)
    out = filled * (1 - k) + soft * k
    return out[CROP:, CROP:]


def extract_mark(src_dir, bg_full, name, box, color):
    """Alpha-matte a flat-coloured mark (header or logo) against the clean background."""
    img = load(src_dir, name)
    x0, y0, x1, y1 = box
    im, bg = img[y0:y1, x0:x1], bg_full[y0:y1, x0:x1]
    color = np.asarray(color, np.float32)
    a = ((im - bg) * (color - bg)).sum(-1) / np.maximum(((color - bg) ** 2).sum(-1), 1)
    a = np.clip(a, 0, 1)
    a[a < 0.12] = 0
    return a


def extract_light_mark(img, box):
    """Alpha-matte a white/grey mark using the min channel against a locally inpainted estimate."""
    x0, y0, x1, y1 = box
    mn = img[y0:y1, x0:x1].min(-1)
    mask = cv2.dilate((mn > 140).astype(np.uint8), np.ones((5, 5), np.uint8))
    est = cv2.inpaint(np.clip(mn, 0, 255).astype(np.uint8), mask * 255, 9, cv2.INPAINT_TELEA)
    est = cv2.GaussianBlur(est.astype(np.float32), (0, 0), 3)
    a = np.clip((mn - est) / np.maximum(255 - est, 1), 0, 1)
    a = np.clip((a - 0.12) / 0.8, 0, 1)
    return a


def build(src_dir):
    bg = clean_background(src_dir)
    full = np.zeros((bg.shape[0] + CROP, bg.shape[1] + CROP, 3), np.float32)
    full[CROP:, CROP:] = bg
    header = extract_mark(src_dir, full, "slide2.jpg", HEADER, (12, 8, 10))
    logo = extract_light_mark(load(src_dir, "slide1.jpg"), LOGO)
    return bg, header, logo


if __name__ == "__main__":
    import sys
    bg, header, logo = build(sys.argv[1])
    out = sys.argv[2]
    Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8)).save(f"{out}_bg.png")
    Image.fromarray((header * 255).astype(np.uint8)).save(f"{out}_header.png")
    Image.fromarray((logo * 255).astype(np.uint8)).save(f"{out}_logo.png")
