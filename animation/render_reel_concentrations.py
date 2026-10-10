"""Render the "niveaux de concentrés parfumants" Instagram reel from the carousel slides.

Usage: python3 render_reel_concentrations.py <slides_dir> <out.mp4> [--preview]

The slides' photo is recovered without text (see carousel_assets.py) and animated
with a slow camera move, while the boxes and captions are re-typeset and animated
on top in the carousel's own style.
"""
import os
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from carousel_assets import build
from render_logo import ease_in_out, ease_out_back, ease_out_cubic

W, H, FPS = 1080, 1920, 30
HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "fonts", "Inter.ttf")
PILL = (43, 11, 16)
PINK = (234, 172, 195)
INK = (10, 4, 4)

SCENES = [
    ("hook", 4.4, {"caption": ["COMPRENDRE LES DIFFÉRENTS", "NIVEAUX DE CONCENTRÉS", "PARFUMANTS"]}),
    ("grid", 6.2, {}),
    ("detail", 5.4, {"box": ("EAU FRAÎCHE", "1 À 3%"),
                     "caption": ["QUASI PAS D’ALCOOL ET TRÈS", "ÉPHÉMÈRE"]}),
    ("detail", 5.8, {"box": ("EAU DE COLOGNE", "2 À 8%"),
                     "caption": ["TRÈS VOLATILE, EFFET FRAIS,", "TENUE 2H, SE RÉAPPLIQUE DANS LA", "JOURNÉE"]}),
    ("detail", 5.8, {"box": ("BRUMES", "1 À 5%"),
                     "caption": ["S’UTILISE EN COMPLÉMENT D’UN", "PARFUM ET A UNE TENUE COURTE", "(1 À 2 HEURES)"]}),
    ("end", 3.6, {}),
]
GRID = [("EAU FRAÎCHE", "1 À 3%"), ("EAU DE COLOGNE", "2 À 8%"), ("BRUMES", "1 À 5%"),
        ("EAU DE TOILETTE", "5 À 15%"), ("EAU DE PARFUM", "10 À 20%"),
        ("EXTRAIT DE PARFUM /\nPARFUM", "20 À 30%")]


def font(size, weight):
    f = ImageFont.truetype(FONT, size)
    f.set_variation_by_axes([min(32, max(14, size)), weight])
    return f


def to_sprite(img):
    a = np.asarray(img, np.float32) / 255
    return np.concatenate([a[..., :3] * a[..., 3:4] * 255, a[..., 3:4]], -1)


def pill_line(text):
    size = 52
    f = font(size, 700)
    while f.getlength(text) > 940:
        size -= 2
        f = font(size, 700)
    tw = f.getlength(text)
    pw, ph = int(tw + 46), 84
    img = Image.new("RGBA", (pw + 4, ph + 4), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    dr.rounded_rectangle([2, 2, pw + 1, ph + 1], radius=22, fill=PILL + (255,))
    dr.text(((pw + 4) / 2, (ph + 4) / 2 + 1), text, font=f, fill=(255, 255, 255, 255), anchor="mm")
    return to_sprite(img)


def pink_box(label, value, w=446, h=180):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    dr.rectangle([0, 0, w - 1, h - 1], fill=INK + (255,))
    dr.rectangle([4, 4, w - 5, h - 5], fill=PINK + (255,))
    fl, fv = font(30, 400), font(31, 700)
    lines = label.split("\n")
    total = 40 * len(lines) + 40
    y = h / 2 - total / 2 + 20
    for ln in lines:
        dr.text((w / 2, y), ln, font=fl, fill=INK + (255,), anchor="mm")
        y += 40
    dr.text((w / 2, y), value, font=fv, fill=INK + (255,), anchor="mm")
    return to_sprite(img)


def paste(frame, sprite, cx, cy, scale=1.0, alpha=1.0):
    if alpha <= 0.003:
        return
    if abs(scale - 1) > 1e-3:
        h, w = sprite.shape[:2]
        sprite = cv2.resize(sprite, (max(1, round(w * scale)), max(1, round(h * scale))),
                            interpolation=cv2.INTER_LINEAR)
    h, w = sprite.shape[:2]
    x, y = int(round(cx - w / 2)), int(round(cy - h / 2))
    fx0, fy0, fx1, fy1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if fx0 >= fx1 or fy0 >= fy1:
        return
    s = sprite[fy0 - y:fy1 - y, fx0 - x:fx1 - x] * alpha
    frame[fy0:fy1, fx0:fx1] = s[..., :3] + frame[fy0:fy1, fx0:fx1] * (1 - s[..., 3:4])


def mark_sprite(alpha, color, scale):
    a = cv2.resize(alpha, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    a = np.clip(a, 0, 1)[..., None]
    return np.concatenate([np.broadcast_to(np.asarray(color, np.float32), a.shape[:2] + (3,)) * a, a], -1)


BG = HEADER = LOGO = None
ASSETS = {}
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
VIGNETTE = 1 - 0.38 * np.clip(np.hypot((XX - W / 2) / W, (YY - H / 2) / H * 0.9) * 1.5 - 0.25, 0, 1) ** 1.6


def init(src_dir):
    global BG, HEADER, LOGO
    BG, header, logo = build(src_dir)
    HEADER = mark_sprite(header, INK, 1.15)
    LOGO = mark_sprite(logo, (255, 255, 255), 2.0)
    for i, (_, _, cfg) in enumerate(SCENES):
        ASSETS[i] = {
            "caption": [pill_line(t) for t in cfg.get("caption", [])],
            "box": pink_box(*cfg["box"]) if "box" in cfg else None,
        }
    ASSETS["grid"] = [pink_box(*g) for g in GRID]


def windows():
    out, t = [], 0.0
    for i, (kind, d, _) in enumerate(SCENES):
        out.append((i, kind, t, d))
        t += d
    return out, t


WINDOWS, TOTAL = windows()


def background(t):
    """Slow camera move across the photo, with a horizontal whip blur at each cut."""
    bh, bw = BG.shape[:2]
    p = t / TOTAL
    zoom = 1920 / bh * (1.10 + 0.06 * np.sin(p * np.pi))
    cx = bw * (0.36 + 0.26 * ease_in_out(p))
    cy = bh * (0.52 - 0.04 * np.sin(p * np.pi * 1.5))
    # Whip: quick sideways push around each scene change.
    whip = 0.0
    for _, _, start, _ in WINDOWS[1:]:
        whip += np.exp(-((t - start) / 0.16) ** 2)
    cx += bw * 0.035 * sum(np.tanh((t - s) / 0.15) for _, _, s, _ in WINDOWS[1:]) / len(WINDOWS)
    m = np.float32([[zoom, 0, W / 2 - cx * zoom], [0, zoom, H / 2 - cy * zoom]])
    frame = cv2.warpAffine(BG, m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if whip > 0.02:
        k = int(6 + 70 * whip) | 1
        kernel = np.zeros((1, k), np.float32)
        kernel[0] = 1.0 / k
        frame = cv2.filter2D(frame, -1, kernel)
        frame = frame * (1 + 0.18 * whip)
    # Breathing warm light.
    glow = 1 + 0.05 * np.sin(t * 1.3) + 0.03 * np.sin(t * 3.1)
    frame = frame * glow * VIGNETTE[..., None]
    return frame


def element_alpha(lt, d, start, dur=0.45):
    """Fade/scale-in progress and exit factor for an element appearing at `start`."""
    p = (lt - start) / dur
    if p <= 0:
        return 0.0, 0.0
    out = 1 - ease_in_out((lt - (d - 0.38)) / 0.32)
    return float(np.clip(p, 0, 1)), float(np.clip(out, 0, 1))


def draw_caption(frame, pills, lt, d, top, start):
    step = 76
    for k, sp in enumerate(pills):
        p, out = element_alpha(lt, d, start + k * 0.14)
        if p <= 0:
            continue
        sc = 0.82 + 0.18 * ease_out_back(p, 1.6)
        cy = top + k * step + sp.shape[0] / 2 - 26 * (1 - out)
        paste(frame, sp, W / 2, cy, sc, ease_out_cubic(p * 1.6) * out)


def draw_scene(frame, i, kind, lt, d):
    a = ASSETS[i]
    if kind == "hook":
        draw_caption(frame, a["caption"], lt, d, 820, 0.35)
    elif kind == "grid":
        boxes = ASSETS["grid"]
        for k, b in enumerate(boxes):
            col, row = k % 2, k // 2
            p, out = element_alpha(lt, d, 0.25 + k * 0.22, 0.5)
            if p <= 0:
                continue
            cx = 50 + 223 + col * 547
            cy = 640 + row * 270 + 40 * (1 - ease_out_cubic(p)) - 26 * (1 - out)
            paste(frame, b, cx, cy, 0.94 + 0.06 * ease_out_cubic(p), ease_out_cubic(p * 1.5) * out)
    elif kind == "detail":
        p, out = element_alpha(lt, d, 0.2, 0.55)
        if p > 0:
            cy = 660 - 60 * (1 - ease_out_back(p, 1.2)) - 26 * (1 - out)
            paste(frame, a["box"], W / 2, cy, 1.2, ease_out_cubic(p * 1.5) * out)
        draw_caption(frame, a["caption"], lt, d, 900, 0.9)
    elif kind == "end":
        dim = 1 - 0.5 * ease_in_out(lt / 0.8)
        frame *= dim
        p = (lt - 0.15) / 1.0
        if p > 0:
            paste(frame, LOGO, W / 2, H / 2 - 40, 0.9 + 0.1 * ease_out_cubic(p), ease_out_cubic(p))


def render_frame(n):
    t = n / FPS
    frame = background(t)
    # Header stays on screen except on the end card.
    end_start = WINDOWS[-1][2]
    ha = ease_out_cubic((t - 0.1) / 0.6) * (1 - ease_in_out((t - end_start + 0.2) / 0.4))
    paste(frame, HEADER, W / 2, 268, 1.0, float(ha))
    for i, kind, start, d in WINDOWS:
        if start <= t < start + d:
            draw_scene(frame, i, kind, t - start, d)
    frame += np.random.default_rng(n).normal(0, 2.2, (H, W, 1)).astype(np.float32)
    env = min(ease_in_out(t / 0.35), ease_in_out((TOTAL - t) / 0.5))
    frame *= env
    return np.clip(frame, 0, 255).astype(np.uint8).tobytes()


def main():
    src, out = sys.argv[1], sys.argv[2]
    init(src)
    if "--preview" in sys.argv:
        for i, kind, start, d in WINDOWS:
            for frac in (0.15, 0.6):
                img = Image.frombytes("RGB", (W, H), render_frame(int((start + d * frac) * FPS)))
                img.save(f"{out}_{i}_{frac}.png")
        return
    n = int(TOTAL * FPS)
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for buf in pool.imap(render_frame, range(n), chunksize=4):
            ff.stdin.write(buf)
    ff.stdin.close()
    ff.wait()


if __name__ == "__main__":
    main()
