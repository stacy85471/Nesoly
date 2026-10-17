"""Ultra-sharp 4K version of a metro mockup.

The photo is upscaled x4 with the EDSR super-resolution network, the poster is pasted at that size
from its full-resolution render (so the logo stays crisp), then the result is brought down to 4K width.

Usage: python3 mockup_4k.py <scene> <photo.jpg> <EDSR_x4.pb> [width]
       e.g. python3 mockup_4k.py escalier source/metro_escalier.jpg EDSR_x4.pb 2160
       -> out/mockup_<scene>_4k.jpg

EDSR_x4.pb: https://raw.githubusercontent.com/Saafke/EDSR_Tensorflow/master/models/EDSR_x4.pb
The x4 upscale is slow on CPU (tens of minutes) and is cached in cache/.
"""
import os
import sys

import cv2
import numpy as np

from mockup_metro import OUT, SCENES, paste

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
TILE, PAD = 256, 16


def upscale_x4(img, model):
    sr = cv2.dnn_superres.DnnSuperResImpl_create()
    sr.readModel(model)
    sr.setModel("edsr", 4)
    h, w = img.shape[:2]
    res = np.zeros((h * 4, w * 4, 3), np.uint8)
    # Overlapping tiles keep memory low and avoid seams.
    for y in range(0, h, TILE):
        for x in range(0, w, TILE):
            y0, x0 = max(y - PAD, 0), max(x - PAD, 0)
            y1, x1 = min(y + TILE + PAD, h), min(x + TILE + PAD, w)
            up = sr.upsample(img[y0:y1, x0:x1])
            th, tw = (min(y + TILE, h) - y) * 4, (min(x + TILE, w) - x) * 4
            res[y * 4:y * 4 + th, x * 4:x * 4 + tw] = up[(y - y0) * 4:(y - y0) * 4 + th, (x - x0) * 4:(x - x0) * 4 + tw]
        print(f"upscale {min(y + TILE, h)}/{h}", flush=True)
    return res


def main():
    scene, photo_path, model = sys.argv[1:4]
    width = int(sys.argv[4]) if len(sys.argv) > 4 else 2160
    os.makedirs(CACHE, exist_ok=True)
    cached = os.path.join(CACHE, os.path.splitext(os.path.basename(photo_path))[0] + "_x4.png")
    if os.path.exists(cached):
        big = cv2.imread(cached)
    else:
        big = upscale_x4(cv2.imread(photo_path), model)
        cv2.imwrite(cached, big)

    for name, corners in SCENES[scene]:
        big = paste(big, cv2.imread(os.path.join(OUT, name + ".png")), corners, scale=4)

    h, w = big.shape[:2]
    img = cv2.resize(big, (width, round(h * width / w)), interpolation=cv2.INTER_AREA)
    # Light unsharp mask for crisp tile joints and edges, without halos.
    blur = cv2.GaussianBlur(img, (0, 0), 1.2)
    img = cv2.addWeighted(img, 1.35, blur, -0.35, 0)
    out = os.path.join(OUT, f"mockup_{scene}_4k.jpg")
    cv2.imwrite(out, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    print(out, img.shape[1], "x", img.shape[0])


if __name__ == "__main__":
    main()
