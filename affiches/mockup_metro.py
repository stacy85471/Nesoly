"""Paste the rendered posters into photos of metro poster frames (perspective + lighting).

Usage: python3 mockup_metro.py source/metro_couloir.jpg source/metro_quai.jpg
       -> out/mockup_couloir.jpg, out/mockup_quai.jpg

The frame corners below match the two reference photos (couloir: 2000x923, quai: 923x2000).
"""
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

# (poster, corners TL, TR, BR, BL in photo pixels)
SCENES = {
    "couloir": [
        ("nesoly_affiche_expo_paysage", [(25, 357), (318, 315), (393, 815), (97, 762)]),
        ("nesoly_affiche_rituel_paysage", [(352, 303), (922, 205), (990, 895), (432, 830)]),
        # Third frame runs past the edge of the photo: corners extrapolated from the visible part.
        ("nesoly_affiche_expo_paysage", [(1003, 183), (2350, -60), (2450, 1330), (1100, 1015)]),
    ],
    "quai": [
        ("nesoly_affiche_rituel_paysage", [(100, 747), (857, 752), (849, 1279), (118, 1320)]),
    ],
}


def paste(photo, poster, corners):
    h, w = photo.shape[:2]
    ph, pw = poster.shape[:2]
    dst = np.float32(corners)
    m = cv2.getPerspectiveTransform(np.float32([(0, 0), (pw, 0), (pw, ph), (0, ph)]), dst)
    warped = cv2.warpPerspective(poster, m, (w, h), flags=cv2.INTER_AREA, borderMode=cv2.BORDER_CONSTANT)
    mask = cv2.warpPerspective(np.full((ph, pw), 255, np.uint8), m, (w, h), flags=cv2.INTER_AREA)
    mask = cv2.GaussianBlur(mask, (3, 3), 0).astype(np.float32)[..., None] / 255

    # Lighting: the brightest paper in the original poster gives the local light level and colour cast.
    paper = cv2.dilate(photo, np.ones((61, 61), np.uint8))
    paper = cv2.GaussianBlur(paper.astype(np.float32), (0, 0), 45)
    light = paper / 238.0
    lit = np.clip(warped.astype(np.float32) * light, 0, 255)
    lit = cv2.GaussianBlur(lit, (0, 0), 0.7)  # match the photo's softness
    noise = np.random.default_rng(0).normal(0, 2.5, lit.shape).astype(np.float32)
    lit = np.clip(lit + noise, 0, 255)
    return (photo * (1 - mask) + lit * mask).astype(np.uint8)


def main():
    photos = dict(zip(["couloir", "quai"], sys.argv[1:3]))
    for scene, path in photos.items():
        img = cv2.imread(path)
        for name, corners in SCENES[scene]:
            poster = cv2.imread(os.path.join(OUT, name + ".png"))
            # Pre-shrink so the perspective warp samples a sensible amount of the 3x render.
            target = max(np.ptp([c[0] for c in corners]), np.ptp([c[1] for c in corners])) * 2
            k = target / max(poster.shape[:2])
            if k < 1:
                poster = cv2.resize(poster, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
            img = paste(img, poster, corners)
        out = os.path.join(OUT, f"mockup_{scene}.jpg")
        cv2.imwrite(out, img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(out)


if __name__ == "__main__":
    main()
