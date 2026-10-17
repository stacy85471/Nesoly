"""Paste the rendered posters into photos of metro poster frames (perspective + lighting).

Usage: python3 mockup_metro.py source/metro_couloir.jpg source/metro_quai.jpg source/metro_escalier.jpg
       -> out/mockup_couloir.jpg, out/mockup_quai.jpg, out/mockup_escalier.jpg

The frame corners below match the reference photos (couloir: 2000x923, quai: 923x2000, escalier: 864x1872).
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
        ("nesoly_affiche_paysage", [(25, 357), (318, 315), (393, 815), (97, 762)]),
        ("nesoly_affiche_paysage", [(352, 303), (922, 205), (990, 895), (432, 830)]),
        # Third frame runs past the edge of the photo: corners extrapolated from the visible part.
        ("nesoly_affiche_paysage", [(1003, 183), (2350, -60), (2450, 1330), (1100, 1015)]),
    ],
    "quai": [
        ("nesoly_affiche_paysage", [(100, 747), (857, 752), (849, 1279), (118, 1320)]),
    ],
    # The left edge of this frame is cut by the photo: the poster runs slightly past it.
    "escalier": [
        ("nesoly_affiche_paysage", [(-3, 759), (475, 763), (473, 1073), (29, 1157)]),
    ],
}


def paste(photo, poster, corners, scale=1):
    """scale: how many times larger `photo` is than the reference photo the corners were measured on."""
    h, w = photo.shape[:2]
    ph, pw = poster.shape[:2]
    dst = np.float32(corners) * scale
    m = cv2.getPerspectiveTransform(np.float32([(0, 0), (pw, 0), (pw, ph), (0, ph)]), dst)
    warped = cv2.warpPerspective(poster, m, (w, h), flags=cv2.INTER_AREA, borderMode=cv2.BORDER_CONSTANT)
    mask = cv2.warpPerspective(np.full((ph, pw), 255, np.uint8), m, (w, h), flags=cv2.INTER_AREA)
    mask = cv2.GaussianBlur(mask, (0, 0), 0.5 * scale).astype(np.float32)[..., None] / 255

    # Lighting: the brightest paper in the original poster gives the local light level and colour cast.
    # Worked out at reference size, so the kernels below keep their meaning whatever the scale.
    small = cv2.resize(photo, (round(w / scale), round(h / scale)), interpolation=cv2.INTER_AREA) if scale != 1 else photo
    paper = cv2.dilate(small, np.ones((161, 161), np.uint8))
    paper = cv2.GaussianBlur(paper.astype(np.float32), (0, 0), 90)
    light = cv2.resize(paper, (w, h), interpolation=cv2.INTER_CUBIC) / 238.0 if scale != 1 else paper / 238.0
    lit = np.clip(warped.astype(np.float32) * light, 0, 255)
    lit = cv2.GaussianBlur(lit, (0, 0), 0.7 * scale)  # match the photo's softness
    noise = np.random.default_rng(0).normal(0, 2.5, lit.shape).astype(np.float32)
    lit = np.clip(lit + noise, 0, 255)
    return (photo * (1 - mask) + lit * mask).astype(np.uint8)


def main():
    photos = dict(zip(["couloir", "quai", "escalier"], sys.argv[1:4]))
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
