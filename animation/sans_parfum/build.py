"""Build the self-contained nesoly_sans_parfum.html from template.html.

- Photos in photos/ are cropped to the arch window and turned into brown/cream duotones.
- Any Chillax / Now font files dropped in fonts/ (woff2, woff, otf or ttf) are embedded.

Usage: python3 build.py
"""
import base64
import io
import os
import re

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
BROWN = np.array([62, 46, 49], np.float32)
CREAM = np.array([242, 237, 230], np.float32)
ARCH_RATIO = 600 / 820

# photo key -> (file, vertical centre of the crop as a fraction of the height, or an explicit crop box)
PHOTOS = {
    # Tight crop on the rain shower: keeps the other brands' bottles out of frame.
    "EAU": ("eau_douche.webp", (100, 0, 620, 711)),
    "HUILE": ("huile_mains.webp", 0.5),
    "SIGNATURE": ("signature_creme.webp", 0.6),
    "CHALEUR": ("chaleur_peignoir.webp", 0.42),
}
WEIGHTS = {"thin": 100, "extralight": 200, "light": 300, "regular": 400, "book": 400, "medium": 500,
           "semibold": 600, "bold": 700, "extrabold": 800, "black": 900}
FORMATS = {".woff2": "woff2", ".woff": "woff", ".otf": "opentype", ".ttf": "truetype"}


def duotone(path, cy):
    img = Image.open(path).convert("RGB")
    if isinstance(cy, tuple):
        img = img.crop(cy)
    else:
        w, h = img.size
        ch = min(h, round(w / ARCH_RATIO))
        top = int(np.clip(cy * h - ch / 2, 0, h - ch))
        img = img.crop((0, top, w, top + ch))
    img = img.resize((720, round(720 / ARCH_RATIO)), Image.LANCZOS)
    lum = np.asarray(img.convert("L").filter(ImageFilter.GaussianBlur(0.4)), np.float32) / 255
    lo, hi = np.percentile(lum, [2, 98])
    v = np.clip((lum - lo) / max(hi - lo, 1e-3), 0, 1)
    v = v * v * (3 - 2 * v) * 0.85 + v * 0.15  # gentle S-curve
    rgb = BROWN + (CREAM - BROWN) * v[..., None]
    buf = io.BytesIO()
    Image.fromarray(rgb.astype(np.uint8)).save(buf, "JPEG", quality=84, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def font_faces():
    rules = []
    fdir = os.path.join(HERE, "fonts")
    if not os.path.isdir(fdir):
        return ""
    for name in sorted(os.listdir(fdir)):
        stem, ext = os.path.splitext(name)
        if ext.lower() not in FORMATS:
            continue
        low = stem.lower().replace("-", "").replace("_", "").replace(" ", "")
        if low.startswith("chillax"):
            family = "Chillax"
        elif low.startswith("now"):
            family = "Now"
        else:
            continue
        rest = low[len(family):]
        if "variable" in rest:
            weight = "100 900"
        else:
            weight = next((str(v) for k, v in sorted(WEIGHTS.items(), key=lambda kv: -len(kv[0])) if k in rest), "400")
        style = "italic" if "italic" in rest else "normal"
        data = base64.b64encode(open(os.path.join(fdir, name), "rb").read()).decode()
        mime = "font/" + {"opentype": "otf", "truetype": "ttf"}.get(FORMATS[ext.lower()], FORMATS[ext.lower()])
        rules.append(f'@font-face {{ font-family: "{family}"; font-weight: {weight}; font-style: {style}; '
                     f'font-display: block; src: url(data:{mime};base64,{data}) format("{FORMATS[ext.lower()]}"); }}')
        print("embedded font:", name, family, weight, style)
    return "\n".join(rules)


def main():
    html = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    html = html.replace("/*__FONT_FACES__*/", font_faces())
    for key, (fname, cy) in PHOTOS.items():
        html = html.replace(f"__PHOTO_{key}__", duotone(os.path.join(HERE, "photos", fname), cy))
    out = os.path.join(HERE, "nesoly_sans_parfum.html")
    open(out, "w", encoding="utf-8").write(html)
    print(out, f"{os.path.getsize(out) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
