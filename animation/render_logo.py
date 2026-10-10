"""Render an animated version of the nesoly logo to MP4.

Usage: python3 render_logo.py <source_logo.png> <out_dir>
Produces nesoly_logo_16x9.mp4 (1920x1080) and nesoly_logo_9x16.mp4 (1080x1920).
"""
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter

FPS = 30
DURATION = 6.0
LOGO_RGB = np.array([245, 240, 234], dtype=np.float32)
BG_CENTER = np.array([142, 121, 116], dtype=np.float32)
PAD = 60
BG_EDGE = np.array([78, 62, 60], dtype=np.float32)


def extract_letters(src):
    """Isolate the cream lettering from the photo and split it into glyphs."""
    im = np.array(Image.open(src).convert("RGB")).astype(np.float32)
    alpha = np.clip((im.min(-1) - 140) / 75, 0, 1)
    ys, xs = np.where(alpha > 0.5)
    alpha = alpha[ys.min() - 4:ys.max() + 5, xs.min() - 4:xs.max() + 5]
    cols = (alpha > 0.5).any(0)
    segs, start = [], None
    for i, c in enumerate(cols):
        if c and start is None:
            start = i
        elif not c and start is not None:
            segs.append((start, i))
            start = None
    if start is not None:
        segs.append((start, len(cols)))
    return alpha, segs


def upscale_alpha(alpha, scale):
    h, w = alpha.shape
    img = Image.fromarray((alpha * 255).astype(np.uint8))
    big = np.array(img.resize((round(w * scale), round(h * scale)), Image.LANCZOS),
                   dtype=np.float32) / 255
    # Re-sharpen edges softened by resampling.
    t = np.clip((big - 0.25) / 0.5, 0, 1)
    return t * t * (3 - 2 * t)


def ease_out_cubic(t):
    t = np.clip(t, 0, 1)
    return 1 - (1 - t) ** 3


def ease_out_back(t, s=1.3):
    t = np.clip(t, 0, 1) - 1
    return 1 + (s + 1) * t ** 3 + s * t ** 2


def ease_in_out(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def background(w, h, t):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # Slowly drifting soft light.
    cx = w * (0.45 + 0.08 * np.sin(t * 0.6))
    cy = h * (0.42 + 0.05 * np.cos(t * 0.5))
    d = np.sqrt(((xx - cx) / w) ** 2 + ((yy - cy) / h) ** 2 * (h / w) ** 2 * 1.6)
    k = np.clip(d / 0.75, 0, 1)[..., None]
    return BG_CENTER * (1 - k) + BG_EDGE * k


def render(src, out_path, w, h, logo_width_frac):
    alpha, segs = extract_letters(src)
    scale = w * logo_width_frac / alpha.shape[1]
    big = upscale_alpha(alpha, scale)
    bh, bw = big.shape
    ox, oy = (w - bw) // 2, (h - bh) // 2

    glyphs = []
    for x0, x1 in segs:
        gx0 = max(int(x0 * scale) - 3, 0)
        gx1 = min(int(x1 * scale) + 3, bw)
        g = np.zeros((bh, bw), np.float32)
        g[:, gx0:gx1] = big[:, gx0:gx1]
        glyphs.append(np.pad(g, PAD))

    grain_rng = np.random.default_rng(7)
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow",
         "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path],
        stdin=subprocess.PIPE)

    rise = 0.06 * bh
    n_frames = int(DURATION * FPS)
    for f in range(n_frames):
        t = f / FPS
        frame = background(w, h, t)
        layer = np.zeros((h, w), np.float32)

        for i, g in enumerate(glyphs):
            start = 0.35 + i * 0.13
            p = (t - start) / 0.9
            if p <= 0:
                continue
            fade = ease_out_cubic(p * 1.4)
            dy = int(round((1 - ease_out_back(p)) * rise))
            blur = float((1 - ease_out_cubic(p * 1.2)) * 10 * scale)
            ga = g
            if blur > 0.3:
                ga = np.array(Image.fromarray((g * 255).astype(np.uint8))
                              .filter(ImageFilter.GaussianBlur(blur)), np.float32) / 255
            y0, x0 = oy + dy - PAD, ox - PAD
            gh, gw = ga.shape
            ys0, ys1 = max(y0, 0), min(y0 + gh, h)
            xs0, xs1 = max(x0, 0), min(x0 + gw, w)
            layer[ys0:ys1, xs0:xs1] = np.maximum(
                layer[ys0:ys1, xs0:xs1], ga[ys0 - y0:ys1 - y0, xs0 - x0:xs1 - x0] * fade)

        # Slow settle zoom once the word is formed.
        z = 1 + 0.025 * ease_in_out((t - 2.2) / (DURATION - 2.2))
        if z > 1.0005:
            li = Image.fromarray((layer * 255).astype(np.uint8))
            cw, ch = round(w / z), round(h / z)
            l0, t0 = (w - cw) // 2, (h - ch) // 2
            layer = np.array(li.crop((l0, t0, l0 + cw, t0 + ch)).resize((w, h), Image.LANCZOS),
                             np.float32) / 255

        # Soft glow under the letters.
        glow_strength = 0.18 * ease_out_cubic((t - 1.0) / 1.5)
        if glow_strength > 0:
            small = Image.fromarray((layer * 255).astype(np.uint8)).resize((w // 8, h // 8))
            glow = np.array(small.filter(ImageFilter.GaussianBlur(6)).resize((w, h), Image.BILINEAR),
                            np.float32) / 255
            frame = frame + (LOGO_RGB - frame) * (glow * glow_strength)[..., None]

        # Light sheen sweeping across the word.
        color = np.broadcast_to(LOGO_RGB, frame.shape).copy()
        sp = (t - 2.3) / 1.1
        if 0 < sp < 1:
            xx = np.arange(w, dtype=np.float32)[None, :]
            yy = np.arange(h, dtype=np.float32)[:, None]
            cx = ox - 0.2 * bw + sp * 1.4 * bw
            band = np.exp(-(((xx + (yy - h / 2) * 0.35) - cx) / (0.06 * bw)) ** 2)
            color = color + (255 - color) * (band * 0.9)[..., None]

        frame = frame + (color - frame) * layer[..., None]
        frame += grain_rng.normal(0, 1.5, (h, w, 1)).astype(np.float32)

        # Fade in from and out to black at the ends.
        env = min(ease_in_out(t / 0.4), ease_in_out((DURATION - t) / 0.5))
        frame *= env
        ff.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())

    ff.stdin.close()
    ff.wait()


if __name__ == "__main__":
    src, out_dir = sys.argv[1], sys.argv[2]
    render(src, f"{out_dir}/nesoly_logo_16x9.mp4", 1920, 1080, 0.52)
    render(src, f"{out_dir}/nesoly_logo_9x16.mp4", 1080, 1920, 0.78)
