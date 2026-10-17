"""Render the nesoly metro posters (PNG + print PDF) with headless Chromium.

Usage: python3 build_affiches.py            -> out/*.png and out/*.pdf
       python3 build_affiches.py --html     -> also keeps the intermediate HTML in out/

Layouts: the cream logo and the slogan "Réconfort olfactif" on nesoly brown, in two formats:
- paysage : 4:3 landscape (4 x 3 m metro format).
- portrait: 120 x 176 cm.
"""
import os
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
FONTS = os.path.join(HERE, "..", "animation", "fonts")
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
LOGO = open(os.path.join(HERE, "nesoly_logo.svg")).read()
SCALE = 3  # PNG pixels per CSS pixel

BASE_CSS = f"""
@font-face {{ font-family: "Jost"; font-weight: 100 900; src: url("file://{FONTS}/Jost.ttf"); }}
:root {{ --cream: #F2EDE6; --brown: #3E2E31; --pink: #EAACC3; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ background: var(--cream); color: var(--brown); font-family: "Jost", sans-serif; }}
.poster {{ position: relative; overflow: hidden; background: var(--cream); }}
.logo svg {{ display: block; width: 100%; height: auto; }}
"""


# Brown background, cream logo and the slogan, nothing else.
def minimal(w, h, logo_w, slogan_px, gap):
    return (w, h, f"""
<style>
.poster {{ background: var(--brown); color: var(--cream); display: flex; flex-direction: column;
          align-items: center; justify-content: center; }}
.logo {{ width: {logo_w}px; }}
.slogan {{ margin-top: {gap}px; font-size: {slogan_px}px; font-weight: 300; letter-spacing: 0.36em;
          text-indent: 0.36em; text-transform: uppercase; }}
</style>
<div class="logo">{LOGO}</div>
<div class="slogan">Réconfort olfactif</div>
""")


POSTERS = {
    "nesoly_affiche_paysage": minimal(1600, 1200, 760, 50, 80),
    "nesoly_affiche_portrait": minimal(1200, 1760, 760, 50, 80),
}


def page_html(w, h, body):
    return (f'<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>{BASE_CSS}'
            f'@page {{ size: {w}px {h}px; margin: 0; }}</style></head>'
            f'<body><div class="poster" style="width:{w}px;height:{h}px">{body}</div></body></html>')


def main():
    os.makedirs(OUT, exist_ok=True)
    keep_html = "--html" in sys.argv
    with sync_playwright() as p:
        kw = {"executable_path": CHROMIUM} if os.path.exists(CHROMIUM) else {}
        browser = p.chromium.launch(**kw)
        for name, (w, h, body) in POSTERS.items():
            html_path = os.path.join(OUT, name + ".html")
            with open(html_path, "w") as f:
                f.write(page_html(w, h, body))
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=SCALE)
            page.goto("file://" + html_path)
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(300)
            page.screenshot(path=os.path.join(OUT, name + ".png"))
            page.pdf(path=os.path.join(OUT, name + ".pdf"), width=f"{w}px", height=f"{h}px", print_background=True)
            page.close()
            if not keep_html:
                os.remove(html_path)
            print(name, f"{w * SCALE}x{h * SCALE}")
        browser.close()


if __name__ == "__main__":
    main()
