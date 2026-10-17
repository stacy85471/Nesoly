"""Trace the cream nesoly wordmark out of source/nesoly_logo.png into a clean SVG.

Usage: python3 vectorize_logo.py   -> writes nesoly_logo.svg (fill="currentColor")
"""
import os

import numpy as np
import potrace
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "animation", "source", "nesoly_logo.png")
SCALE = 6


def main():
    im = np.array(Image.open(SRC).convert("RGB")).astype(np.float32)
    alpha = np.clip((im.min(-1) - 140) / 75, 0, 1)
    ys, xs = np.where(alpha > 0.5)
    alpha = alpha[ys.min() - 4:ys.max() + 5, xs.min() - 4:xs.max() + 5]
    h, w = alpha.shape
    big = Image.fromarray((alpha * 255).astype(np.uint8)).resize((w * SCALE, h * SCALE), Image.LANCZOS)
    big = big.filter(ImageFilter.GaussianBlur(SCALE * 1.5))
    bmp = potrace.Bitmap(np.array(big) <= 127)  # potracer traces the falsy pixels
    path = bmp.trace(turdsize=200, alphamax=1.1, opticurve=True, opttolerance=1.0)
    d = []
    for curve in path:
        s = curve.start_point
        d.append(f"M{s.x / SCALE:.2f} {s.y / SCALE:.2f}")
        for seg in curve.segments:
            e = seg.end_point
            if seg.is_corner:
                d.append(f"L{seg.c.x / SCALE:.2f} {seg.c.y / SCALE:.2f}L{e.x / SCALE:.2f} {e.y / SCALE:.2f}")
            else:
                d.append(f"C{seg.c1.x / SCALE:.2f} {seg.c1.y / SCALE:.2f} {seg.c2.x / SCALE:.2f} {seg.c2.y / SCALE:.2f} "
                         f"{e.x / SCALE:.2f} {e.y / SCALE:.2f}")
        d.append("Z")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" fill="currentColor">'
           f'<path fill-rule="evenodd" d="{"".join(d)}"/></svg>\n')
    open(os.path.join(HERE, "nesoly_logo.svg"), "w").write(svg)
    print("nesoly_logo.svg", w, "x", h, len(path), "curves")


if __name__ == "__main__":
    main()
