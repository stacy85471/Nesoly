"""Render the nesoly "fatigue olfactive" vertical reel (TikTok / Instagram Reels).

Usage: python3 render_reel.py <source_logo.png> <out.mp4> [--preview]

Everything is generated procedurally (bottle, mist, cream, droplets, text),
so no stock footage is needed. Scene durations live in SCENES below and can be
adjusted to match the voice-over.
"""
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter

from render_logo import extract_letters, upscale_alpha, ease_out_back, ease_out_cubic, ease_in_out

W, H = 1080, 1920
FPS = 30
XFADE = 0.8
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_SERIF = os.path.join(HERE, "fonts", "CormorantGaramond.ttf")
FONT_SERIF_IT = os.path.join(HERE, "fonts", "CormorantGaramond-Italic.ttf")
FONT_SANS = os.path.join(HERE, "fonts", "Jost.ttf")

CREAM = np.array([245, 240, 234], np.float32)
GOLD = np.array([212, 176, 138], np.float32)
MOCHA_LIGHT = np.array([150, 126, 116], np.float32)
MOCHA_DARK = np.array([52, 40, 37], np.float32)

# (name, duration in seconds). Each scene overlaps the next by XFADE.
SCENES = [("bottle", 9.5), ("spray", 10.5), ("cream", 7.5), ("ritual", 12.0), ("logo", 5.0)]
NBSP = " "

TEXTS = {
    "bottle": [
        ("title", "Le piège du nez habitué", 0.6),
        ("body", "Deux vaporisations. C’est tout.", 2.4),
        ("body", f"La fatigue olfactive{NBSP}: votre nez s’habitue, mais tout le monde le perçoit encore.", 4.4),
    ],
    "spray": [
        ("title", "Le cercle vicieux", 0.6),
        ("body", "Deux pulvérisations de plus… puis deux autres à midi.", 2.6),
        ("body", f"Huit vaporisations au total. Vous ne sentez rien, les autres si.", 5.6),
    ],
    "cream": [
        ("title", f"La solution{NBSP}: Confiance et Rituels", 0.6),
        ("body", "Un parfum de qualité tient 6 à 10 heures.", 2.6),
    ],
    "ritual": [
        ("title", f"Le Rituel en 4 étapes", 0.6),
        ("step", ("1.", "Nettoyer", "sans parfum"), 2.4),
        ("step", ("2.", "Hydrater", "peau humide"), 4.2),
        ("step", ("3.", "Vaporiser", "deux pressions"), 6.0),
        ("step", ("4.", "Sublimer", "sur les vêtements"), 7.8),
    ],
}

YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
RNG = np.random.default_rng(11)


# --------------------------------------------------------------------------- helpers

def font(path, size, weight):
    f = ImageFont.truetype(path, size)
    f.set_variation_by_axes([weight])
    return f


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def rrect_sdf(X, Y, x0, y0, x1, y1, r):
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    qx = np.abs(X - cx) - ((x1 - x0) / 2 - r)
    qy = np.abs(Y - cy) - ((y1 - y0) / 2 - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def over(dst, src):
    """Premultiplied RGBA 'over' compositing (float arrays, last axis = 4)."""
    a = src[..., 3:4]
    return src + dst * (1 - a)


def layer(rgb, alpha):
    a = np.clip(alpha, 0, 1)[..., None]
    return np.concatenate([np.broadcast_to(rgb, a.shape[:-1] + (3,)) * a, a], -1).astype(np.float32)


def resize_f(arr, size, resample=Image.BILINEAR):
    """Resize a 2-D float array with PIL (mode 'F' needs contiguous float32)."""
    img = Image.fromarray(np.ascontiguousarray(arr, np.float32), "F")
    return np.asarray(img.resize(size, resample), np.float32)


def resize_rgba(sprite, scale):
    h, w = sprite.shape[:2]
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    return np.stack([resize_f(sprite[..., c], (nw, nh)) for c in range(4)], -1)


def paste(frame, sprite, x, y):
    """Composite a premultiplied sprite onto an RGB frame, top-left at (x, y)."""
    h, w = sprite.shape[:2]
    x, y = int(round(x)), int(round(y))
    fx0, fy0, fx1, fy1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if fx0 >= fx1 or fy0 >= fy1:
        return
    s = sprite[fy0 - y:fy1 - y, fx0 - x:fx1 - x]
    frame[fy0:fy1, fx0:fx1] = s[..., :3] + frame[fy0:fy1, fx0:fx1] * (1 - s[..., 3:4])


def fractal_noise(h, w, seed, octaves=(6, 12, 24, 48, 96, 192), falloff=0.55):
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, total = 1.0, 0.0
    for o in octaves:
        small = rng.standard_normal((max(2, h * o // w), o)).astype(np.float32)
        out += amp * resize_f(small, (w, h), Image.BICUBIC)
        total += amp
        amp *= falloff
    out /= total
    return out / (np.abs(out).max() + 1e-6)


# --------------------------------------------------------------------------- assets

def make_bottle(s=1.5, cap=True, droplets=False, logo_alpha=None):
    """Minimal luxury perfume bottle as a premultiplied RGBA sprite (700x1100 * s)."""
    w, h = int(700 * s), int(1100 * s)
    Y, X = np.mgrid[0:h, 0:w].astype(np.float32) / s
    aa = 1.2 / s
    cov = lambda d: np.clip(0.5 - d / aa, 0, 1)
    img = np.zeros((h, w, 4), np.float32)

    bx0, by0, bx1, by1 = 110, 380, 590, 1000
    cx = (bx0 + bx1) / 2
    d_out = rrect_sdf(X, Y, bx0, by0, bx1, by1, 64)
    d_in = rrect_sdf(X, Y, bx0 + 30, by0 + 34, bx1 - 30, by1 - 74, 40)
    u = np.clip((X - cx) / ((bx1 - bx0) / 2), -1, 1)
    cyl = np.sqrt(1 - u ** 2)

    # Liquid.
    lt = 455
    v = np.clip((Y - lt) / (by1 - 74 - lt), 0, 1)[..., None]
    amber = np.array([236, 190, 132], np.float32) * (1 - v) + np.array([176, 108, 62], np.float32) * v
    amber = amber * (0.62 + 0.38 * cyl[..., None])
    glow = np.exp(-(((X - cx + 40) / 150) ** 2 + ((Y - 640) / 220) ** 2))[..., None]
    amber = amber + (np.array([255, 232, 196]) - amber) * glow * 0.55
    liquid_a = cov(d_in) * smoothstep(lt - 1, lt + 1.5, Y) * 0.9
    img = over(img, layer(amber, liquid_a))
    # Meniscus and dip tube.
    img = over(img, layer(np.array([255, 240, 214]), cov(d_in) * np.exp(-((Y - lt) / 2.2) ** 2) * 0.75))
    img = over(img, layer(np.array([255, 245, 230]), (np.abs(X - cx) < 2.5) * (Y < by1 - 80) * (Y > by0 - 30) * 0.22))

    # Glass walls: thin tint in the middle, thicker and brighter near the edges.
    wall = cov(d_out) * (1 - cov(d_in))
    glass_a = cov(d_out) * 0.10 + wall * (0.28 + 0.25 * (1 - cyl))
    img = over(img, layer(np.array([250, 244, 236]), glass_a))
    rim = cov(d_out) * np.exp(np.minimum(d_out, 0) / 2.0) * 0.55
    img = over(img, layer(np.array([255, 250, 244]), rim))

    # Label: the nesoly wordmark printed on the glass.
    if logo_alpha is not None:
        lw = int(250 * s)
        lh = int(logo_alpha.shape[0] * lw / logo_alpha.shape[1])
        la = np.asarray(Image.fromarray((logo_alpha * 255).astype(np.uint8)).resize((lw, lh), Image.LANCZOS),
                        np.float32) / 255
        lab = np.zeros((h, w), np.float32)
        ly, lx = int(700 * s), int(cx * s - lw / 2)
        lab[ly:ly + lh, lx:lx + lw] = la
        img = over(img, layer(CREAM, lab * 0.92))

    # Speculars.
    inside = cov(d_out) * smoothstep(by0 + 20, by0 + 70, Y) * (1 - smoothstep(by1 - 70, by1 - 20, Y))
    spec = np.exp(-((X - (bx0 + 48)) / 9) ** 2) * 0.75 + np.exp(-((X - (bx1 - 40)) / 4) ** 2) * 0.45
    spec += np.exp(-((X - (bx0 + 90)) / 30) ** 2) * 0.12
    img = over(img, layer(np.array([255, 255, 255]), inside * spec))

    if droplets:
        rng = np.random.default_rng(3)
        for _ in range(85):
            r = rng.uniform(3, 10)
            dx, dy = rng.uniform(bx0 + 25, bx1 - 25), rng.uniform(by0 + 40, by1 - 40)
            x0, x1 = int((dx - r - 3) * s), int((dx + r + 3) * s)
            y0, y1 = int((dy - r - 3) * s), int((dy + r + 3) * s)
            sx, sy = X[y0:y1, x0:x1], Y[y0:y1, x0:x1]
            d = np.hypot(sx - dx, (sy - dy) * 0.92) - r
            body = np.clip(0.5 - d * s / 1.2, 0, 1)
            sub = img[y0:y1, x0:x1]
            sub = over(sub, layer(np.array([90, 60, 40]), body * 0.25 * smoothstep(dy - r, dy + r, sy)))
            hl = np.exp(-(((sx - dx + r * 0.35) ** 2 + (sy - dy + r * 0.4) ** 2) / (0.09 * r * r)))
            sub = over(sub, layer(np.array([255, 255, 255]), hl * 0.9 * body))
            img[y0:y1, x0:x1] = sub

    # Gold collar.
    ucol = np.clip((X - 350) / 66, -1, 1)
    gold = GOLD * (0.55 + 0.45 * np.sqrt(1 - ucol ** 2))[..., None]
    gold = gold + (255 - gold) * (np.exp(-((ucol + 0.4) / 0.12) ** 2) * 0.7)[..., None]
    img = over(img, layer(gold, cov(rrect_sdf(X, Y, 284, 338, 416, 386, 6))))

    if cap:
        ucap = np.clip((X - 350) / 115, -1, 1)
        capc = np.array([238, 229, 218], np.float32) * (0.62 + 0.38 * np.sqrt(1 - ucap ** 2))[..., None]
        capc = capc + (255 - capc) * (np.exp(-((ucap + 0.5) / 0.15) ** 2) * 0.35)[..., None]
        capc = capc * (1 - 0.12 * smoothstep(300, 345, Y))[..., None]
        img = over(img, layer(capc, cov(rrect_sdf(X, Y, 235, 110, 465, 345, 20))))
    else:
        ua = np.clip((X - 350) / 44, -1, 1)
        act = GOLD * (0.5 + 0.5 * np.sqrt(1 - ua ** 2))[..., None]
        act = act + (255 - act) * (np.exp(-((ua + 0.45) / 0.15) ** 2) * 0.6)[..., None]
        img = over(img, layer(act, cov(rrect_sdf(X, Y, 306, 262, 394, 342, 12))))
        img = over(img, layer(np.array([40, 28, 22]), cov(np.hypot(X - 386, Y - 292) - 6) * 0.9))
    return img


def make_forearm(s=0.5):
    """Soft, out-of-focus forearm with pearled water droplets (premultiplied RGBA, full frame)."""
    h, w = int(H * s), int(W * s)
    Y, X = np.mgrid[0:h, 0:w].astype(np.float32) / s
    p0, p1, rad = np.array([1350.0, 770.0]), np.array([-300.0, 630.0]), 135.0
    d = p1 - p0
    t = np.clip(((X - p0[0]) * d[0] + (Y - p0[1]) * d[1]) / (d @ d), 0, 1)
    rr = np.hypot(X - (p0[0] + t * d[0]), Y - (p0[1] + t * d[1]))
    r_t = rad * (1 - 0.12 * t)
    a = np.clip((r_t - rr) / 3, 0, 1)
    shade = np.sqrt(np.clip(1 - (rr / r_t) ** 2, 0, 1))
    side = ((X - (p0[0] + t * d[0])) * -d[1] + (Y - (p0[1] + t * d[1])) * d[0]) / np.hypot(*d) / r_t
    skin = np.array([206, 158, 132], np.float32) * (0.35 + 0.65 * shade)[..., None]
    skin = skin + (np.array([255, 226, 204]) - skin) * (np.exp(-((side + 0.45) / 0.25) ** 2) * 0.45 * a)[..., None]
    img = layer(skin, a)
    rng = np.random.default_rng(5)
    for _ in range(40):
        tt, ss = rng.uniform(0.05, 0.9), rng.uniform(-0.75, 0.75)
        c = p0 + tt * d
        n = np.array([-d[1], d[0]]) / np.hypot(*d)
        cxy = c + n * ss * rad * (1 - 0.12 * tt)
        r = rng.uniform(4, 12)
        dd = np.hypot(X - cxy[0], Y - cxy[1])
        body = np.clip((r - dd) / 1.5, 0, 1) * a
        img = over(img, layer(np.array([120, 80, 60]), body * 0.25 * smoothstep(cxy[1] - r, cxy[1] + r, Y)))
        hl = np.exp(-(((X - cxy[0] + r * 0.35) ** 2 + (Y - cxy[1] + r * 0.35) ** 2) / (0.1 * r * r)))
        img = over(img, layer(np.array([255, 255, 255]), hl * body * 0.9))
    img = np.stack([gaussian_filter(img[..., c], 3.5) for c in range(4)], -1)
    return resize_rgba(img, 1 / s)


def make_mist():
    """Particles for four slow-motion sprays (2 + 2)."""
    puffs = [0.9, 1.7, 4.6, 5.4]
    parts = []
    for pt in puffs:
        n = 900
        ang = RNG.normal(0.1, 0.13, n)
        speed = 80 + 1000 * RNG.beta(1.3, 2.8, n)
        parts.append(np.stack([np.full(n, pt) + RNG.uniform(0, 0.25, n),
                               speed * np.cos(ang), speed * np.sin(ang),
                               RNG.uniform(0.6, 1.6, n), RNG.uniform(0, 1, n)], 1))
    return np.concatenate(parts).astype(np.float32)


def render_text_block(kind, content, width=900):
    """Return a premultiplied RGBA array for one text element."""
    if kind == "title":
        f = font(FONT_SERIF, 96, 500)
        lines = wrap(content, f, width)
        lh = 100
        img = Image.new("RGBA", (W, lh * len(lines) + 70), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        for i, ln in enumerate(lines):
            dr.text((W / 2, i * lh + 50), ln, font=f, fill=tuple(int(c) for c in CREAM) + (255,), anchor="mm")
        y = lh * len(lines) + 30
        dr.line([(W / 2 - 40, y), (W / 2 + 40, y)], fill=tuple(int(c) for c in GOLD) + (255,), width=2)
    elif kind == "body":
        f = font(FONT_SANS, 46, 300)
        lines = wrap(content, f, width)
        lh = 64
        img = Image.new("RGBA", (W, lh * len(lines) + 16), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        for i, ln in enumerate(lines):
            dr.text((W / 2, i * lh + lh / 2 + 4), ln, font=f, fill=tuple(int(c) for c in CREAM) + (255,),
                    anchor="mm")
    else:  # step
        num, word, note = content
        fn, fw, fnote = font(FONT_SERIF_IT, 66, 500), font(FONT_SERIF, 66, 500), font(FONT_SANS, 38, 300)
        gap = 22
        parts = [(num, fn, GOLD), (word, fw, CREAM), (note, fnote, CREAM * 0.86)]
        widths = [ImageDraw.Draw(Image.new("L", (1, 1))).textlength(t, font=f) for t, f, _ in parts]
        total = sum(widths) + gap * 2
        img = Image.new("RGBA", (W, 84), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        x = (W - total) / 2
        for (t, f, c), wd in zip(parts, widths):
            dr.text((x, 56), t, font=f, fill=tuple(int(v) for v in c) + (255,), anchor="ls")
            x += wd + gap
    a = np.asarray(img, np.float32) / 255
    rgb, al = a[..., :3] * 255, a[..., 3:4]
    # Soft shadow for legibility on any background.
    sh = gaussian_filter(al[..., 0], 6) * 0.45
    out = np.concatenate([rgb * al, al], -1)
    shadow = np.zeros_like(out)
    shadow[..., 3] = sh
    return over(shadow, out)


def wrap(text, f, width):
    words, lines, cur = text.split(" "), [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if f.getlength(trial) > width and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = trial
    lines.append(cur)
    return lines


def layout_texts():
    out = {}
    for scene, items in TEXTS.items():
        blocks = [(render_text_block(k, c), start) for k, c, start in items]
        y = 1080 if scene != "ritual" else 1010
        placed = []
        for b, start in blocks:
            placed.append((b, y, start))
            y += b.shape[0] + (8 if scene == "ritual" else 18)
        out[scene] = placed
    return out


BOTTLE = BOTTLE_NOCAP = BOTTLE_DROPS = FOREARM = MIST = TEXT = LOGO = WALL = None


def init_assets(logo_src):
    global BOTTLE, BOTTLE_NOCAP, BOTTLE_DROPS, FOREARM, MIST, TEXT, LOGO, WALL
    alpha, _ = extract_letters(logo_src)
    BOTTLE = make_bottle(cap=True, logo_alpha=alpha)
    BOTTLE_NOCAP = make_bottle(cap=False, logo_alpha=alpha)
    BOTTLE_DROPS = make_bottle(cap=True, droplets=True, logo_alpha=alpha)
    FOREARM = make_forearm()
    MIST = make_mist()
    TEXT = layout_texts()
    LOGO = upscale_alpha(alpha, W * 0.66 / alpha.shape[1])
    WALL = fractal_noise(H + 200, W + 200, 1) * 0.6 + fractal_noise(H + 200, W + 200, 2, (300, 600), 0.8) * 0.4


# --------------------------------------------------------------------------- scenes

def background(t, lx=0.5, ly=0.3, pan=(0, 0), surface_y=None):
    ox, oy = int(100 + pan[0]), int(100 + pan[1])
    tex = WALL[oy:oy + H, ox:ox + W]
    d = np.sqrt(((XX - W * lx) / W) ** 2 + ((YY - H * ly) / W) ** 2)
    k = smoothstep(0.0, 1.05, d)[..., None]
    col = MOCHA_LIGHT * (1 - k) + MOCHA_DARK * k
    col = col * (1 + 0.07 * tex[..., None])
    if surface_y is not None:
        top = smoothstep(surface_y - 2, surface_y + 2, YY)
        col = col * (1 - 0.18 * top[..., None])
        col = col + (np.array([255, 236, 214]) - col) * (np.exp(-((YY - surface_y) / 3) ** 2) * 0.10)[..., None]
    return col


def place_bottle(frame, sprite, cx, base_y, scale, sweep=None, shadow=True, reflection=True):
    sp = resize_rgba(sprite, scale / 1.5)
    if sweep is not None:
        h, w = sp.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        band = np.exp(-(((xx + yy * 0.45) - sweep * (w + h * 0.45)) / (0.07 * w)) ** 2) * 0.32
        sp[..., :3] += (255 * sp[..., 3:4] - sp[..., :3]) * band[..., None]
    h, w = sp.shape[:2]
    x = cx - w / 2
    y = base_y - 1000 / 1100 * h
    if shadow:
        sh = np.exp(-(((XX - cx) / (0.42 * w)) ** 2 + ((YY - base_y) / (0.03 * h)) ** 2) * 2.0) * 0.5
        frame *= (1 - sh)[..., None]
    if reflection:
        bottom = sp[int(750 / 1100 * h):int(1000 / 1100 * h)][::-1].copy()
        fade = np.linspace(0.12, 0, bottom.shape[0], dtype=np.float32)[:, None, None]
        paste(frame, bottom * fade, x, base_y + 2)
    paste(frame, sp, x, y)


def scene_bottle(t, d):
    z = 1 + 0.06 * ease_in_out(t / d)
    surface = 1000
    frame = background(t, 0.42 + 0.03 * np.sin(t * 0.4), 0.28, (t * 6, 0), surface)
    place_bottle(frame, BOTTLE, W / 2, surface, 0.9 * z, sweep=(t - 1.2) / 3.0)
    return frame


def scene_spray(t, d):
    frame = background(t, 0.35, 0.3, (t * 4, t * 2))
    frame = frame * 1.0
    # Forearm drifts very slowly (slow-motion parallax).
    paste(frame, FOREARM, -t * 6, -t * 3)
    bscale, bcx, bbase = 0.5, 250 - t * 3, 840
    place_bottle(frame, BOTTLE_NOCAP, bcx, bbase, bscale, shadow=False, reflection=False)
    nozzle = np.array([bcx + (386 - 350) * bscale, bbase - (1000 - 292) * bscale])
    # Mist particles in slow motion.
    age = t - MIST[:, 0]
    m = age > 0
    p = MIST[m]
    a_ = age[m]
    k = 1.6
    travel = (1 - np.exp(-k * a_)) / k
    drift = 40 * a_ * (p[:, 4] - 0.5) + 25 * np.sin(a_ * 1.3 + p[:, 4] * 40) * smoothstep(0, 1.5, a_)
    px = nozzle[0] + p[:, 1] * travel + drift
    py = nozzle[1] + p[:, 2] * travel + drift * 0.7 + 30 * a_ ** 1.5 * p[:, 3]
    life = np.exp(-a_ / 1.8) * smoothstep(0, 0.08, a_)
    hs = 0.5
    grid = np.zeros((int(H * hs), int(W * hs)), np.float32)
    ix, iy = (px * hs).astype(int), (py * hs).astype(int)
    ok = (ix >= 0) & (ix < grid.shape[1]) & (iy >= 0) & (iy < grid.shape[0])
    np.add.at(grid, (iy[ok], ix[ok]), life[ok] * p[ok, 3])
    fine = gaussian_filter(grid, 1.2) * 4.0
    haze = gaussian_filter(grid, 22) * 22
    mist = np.clip(fine + haze, 0, 1)
    mist = resize_f(mist, (W, H))
    frame += (np.array([255, 246, 234]) - frame) * (mist * 0.55)[..., None]
    # Twinkling glints.
    g = ok & (p[:, 4] > 0.94)
    for gx, gy, gl, ph in zip(px[g], py[g], life[g], p[g, 4]):
        tw = gl * (0.5 + 0.5 * np.sin(t * 9 + ph * 50))
        x0, y0 = int(gx), int(gy)
        if 2 <= x0 < W - 2 and 2 <= y0 < H - 2:
            frame[y0 - 1:y0 + 2, x0 - 1:x0 + 2] += (255 - frame[y0 - 1:y0 + 2, x0 - 1:x0 + 2]) * tw * 0.8
    # Warm light leak.
    leak = np.exp(-(((XX - W * 0.95) / 500) ** 2 + ((YY - H * 0.1) / 700) ** 2)) * (0.18 + 0.05 * np.sin(t))
    frame += (np.array([255, 214, 170]) - frame) * leak[..., None]
    return frame


def scene_cream(t, d):
    hs = 0.5
    h, w = int(H * hs), int(W * hs)
    Y, X = np.mgrid[0:h, 0:w].astype(np.float32) / hs
    cx, cy = W * 0.5, 640
    z = 1 + 0.08 * ease_in_out(t / d)
    dx, dy = (X - cx) / z, (Y - cy) / z
    r = np.hypot(dx, dy * 1.15)
    th = np.arctan2(dy, dx) + t * 0.12
    warp = 1 + 0.05 * np.sin(th * 3 + r / 90)
    rn = r * warp
    dome = 260 * np.exp(-(rn / 420) ** 2)
    spiral = np.sin(rn / 26 - th * 1.0 + 0.4 * t) * 34 * np.exp(-(rn / 380) ** 2)
    ripples = 10 * np.sin(X / 70 + 0.6 * np.sin(Y / 140) + t * 0.3) + 6 * np.sin(Y / 55 - t * 0.25)
    hf = dome + spiral + ripples
    gy, gx = np.gradient(hf)
    n = np.stack([-gx * hs * 2, -gy * hs * 2, np.ones_like(hf)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    L = np.array([-0.45, -0.6, 0.66])
    L /= np.linalg.norm(L)
    diff = np.clip(n @ L, 0, 1)
    Hv = L + np.array([0, 0, 1.0])
    Hv /= np.linalg.norm(Hv)
    spec = np.clip(n @ Hv, 0, 1) ** 60
    base = np.array([244, 232, 220], np.float32)
    shadow = np.array([176, 146, 128], np.float32)
    col = shadow + (base - shadow) * (0.25 + 0.75 * diff)[..., None] + 255 * (spec * 0.55)[..., None]
    col = np.clip(col, 0, 255)
    col = np.stack([resize_f(col[..., c], (W, H)) for c in range(3)], -1)
    # Warm, low-key grade and a dark scrim under the text.
    vign = smoothstep(0.3, 1.2, np.hypot((XX - cx) / W, (YY - cy) / W * 0.9))[..., None]
    col = col * (1 - 0.45 * vign)
    scrim = smoothstep(940, 1250, YY)[..., None] * 0.86
    col = col + (MOCHA_DARK * 1.1 - col) * scrim
    return col


BOKEH = RNG.uniform(0, 1, (26, 4)).astype(np.float32)


def scene_ritual(t, d):
    surface = 960
    frame = background(t, 0.5 + 0.12 * np.sin(t * 0.35), 0.26, (50 + 40 * np.sin(t * 0.3), 0), surface)
    # Bokeh drifting opposite to the camera move for a slow orbit feel.
    hs = 0.25
    bk = Image.new("L", (int(W * hs), int(H * hs)), 0)
    dr = ImageDraw.Draw(bk)
    for bx, by, br, ba in BOKEH:
        x = ((bx * 1.4 - 0.2) - 0.18 * np.sin(t * 0.3) * (0.5 + br)) * W * hs
        y = (0.05 + by * 0.5) * H * hs
        r = (18 + 70 * br) * hs
        dr.ellipse([x - r, y - r, x + r, y + r], fill=int(30 + 50 * ba))
    bka = gaussian_filter(np.asarray(bk, np.float32) / 255, 2.5)
    bka = resize_f(bka, (W, H))
    frame += (np.array([255, 222, 180]) - frame) * (bka * 0.55)[..., None]
    z = 0.78 + 0.05 * ease_in_out(t / d)
    place_bottle(frame, BOTTLE_DROPS, W / 2 + 10 * np.sin(t * 0.3), surface, z,
                 sweep=0.5 + 0.55 * np.sin(t * 0.3 - 1.2))
    return frame


def scene_logo(t, d):
    frame = background(t, 0.5, 0.45, (20, 20))
    bh, bw = LOGO.shape
    oy, ox = (H - bh) // 2, (W - bw) // 2
    lay = np.zeros((H, W), np.float32)
    cols = (LOGO > 0.5).any(0)
    edges = np.flatnonzero(np.diff(np.r_[0, cols.astype(int), 0]))
    segs = list(zip(edges[::2], edges[1::2]))
    for i, (x0, x1) in enumerate(segs):
        p = (t - 0.3 - i * 0.12) / 0.9
        if p <= 0:
            continue
        g = np.zeros_like(LOGO)
        g[:, max(x0 - 3, 0):x1 + 3] = LOGO[:, max(x0 - 3, 0):x1 + 3]
        blur = float((1 - ease_out_cubic(p * 1.2)) * 14)
        if blur > 0.3:
            g = gaussian_filter(g, blur)
        dy = int(round((1 - ease_out_back(p)) * 0.08 * bh))
        y0 = oy + dy
        lay[y0:y0 + bh, ox:ox + bw] = np.maximum(lay[y0:y0 + bh, ox:ox + bw], g * ease_out_cubic(p * 1.4))
    glow = gaussian_filter(lay[::4, ::4], 10)
    glow = resize_f(glow, (W, H))
    frame += (CREAM - frame) * (glow * 0.25 * ease_out_cubic((t - 1.0) / 1.5))[..., None]
    frame += (CREAM - frame) * lay[..., None]
    return frame


SCENE_FN = {"bottle": scene_bottle, "spray": scene_spray, "cream": scene_cream,
            "ritual": scene_ritual, "logo": scene_logo}


def scene_windows():
    out, start = [], 0.0
    for name, d in SCENES:
        out.append((name, start, d))
        start += d - XFADE
    return out, start + XFADE


WINDOWS, TOTAL = scene_windows()


def draw_texts(frame, scene, t, d):
    for block, y, start in TEXT.get(scene, []):
        p = (t - start) / 1.0
        if p <= 0:
            continue
        a = ease_out_cubic(p) * (1 - smoothstep(d - XFADE - 0.6, d - XFADE + 0.1, t))
        if a <= 0:
            continue
        dy = (1 - ease_out_cubic(p)) * 26
        paste(frame, block * a, 0, y + dy)


def render_frame(i):
    t = i / FPS
    frame = None
    for name, start, d in WINDOWS:
        lt = t - start
        if lt < 0 or lt > d:
            continue
        f = SCENE_FN[name](lt, d)
        draw_texts(f, name, lt, d)
        wgt = ease_in_out(lt / XFADE) if start > 0 else 1.0
        frame = f if frame is None else frame * (1 - wgt) + f * wgt
    # Global grade: warm tint, grain, fade in/out.
    frame = frame * np.array([1.02, 1.0, 0.97], np.float32)
    frame += np.random.default_rng(i).normal(0, 2.0, (H, W, 1)).astype(np.float32)
    env = min(ease_in_out(t / 0.5), ease_in_out((TOTAL - t) / 0.6))
    frame *= env
    return np.clip(frame, 0, 255).astype(np.uint8).tobytes()


def main():
    logo_src, out = sys.argv[1], sys.argv[2]
    preview = "--preview" in sys.argv
    init_assets(logo_src)
    n = int(TOTAL * FPS)
    if preview:
        for name, start, d in WINDOWS:
            for frac in (0.25, 0.6, 0.95):
                i = int((start + d * frac) * FPS)
                Image.frombytes("RGB", (W, H), render_frame(i)).save(f"{out}_{name}_{frac}.png")
        return
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(n), chunksize=4)):
            ff.stdin.write(buf)
            if k % 150 == 0:
                print(f"{k}/{n}", flush=True)
    ff.stdin.close()
    ff.wait()


if __name__ == "__main__":
    main()
