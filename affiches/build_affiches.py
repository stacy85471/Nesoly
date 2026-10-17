"""Render the nesoly metro posters (PNG + print PDF) with headless Chromium.

Usage: python3 build_affiches.py            -> out/*.png and out/*.pdf
       python3 build_affiches.py --html     -> also keeps the intermediate HTML in out/

Layouts:
- expo_paysage  : 4:3 landscape (4 x 3 m metro format), editorial "exhibition" style.
- expo_portrait : 120 x 176 cm portrait, same style, one photo.
- rituel_paysage: 4:3 landscape, full-bleed photo with the claim on top, product-ad style.
"""
import os
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
FONTS = os.path.join(HERE, "..", "animation", "fonts")
PHOTOS = os.path.join(HERE, "..", "animation", "sans_parfum", "photos")
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
LOGO = open(os.path.join(HERE, "nesoly_logo.svg")).read()
SCALE = 3  # PNG pixels per CSS pixel

BASE_CSS = f"""
@font-face {{ font-family: "Jost"; font-weight: 100 900; src: url("file://{FONTS}/Jost.ttf"); }}
@font-face {{ font-family: "Cormorant"; font-weight: 300 700; font-style: italic;
             src: url("file://{FONTS}/CormorantGaramond-Italic.ttf"); }}
:root {{ --cream: #F2EDE6; --brown: #3E2E31; --pink: #EAACC3; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ background: var(--cream); color: var(--brown); font-family: "Jost", sans-serif; }}
.poster {{ position: relative; overflow: hidden; background: var(--cream); }}
.logo svg {{ display: block; width: 100%; height: auto; }}
.photo {{ background-size: cover; background-repeat: no-repeat; }}
.bw {{ filter: grayscale(1) contrast(1.12) brightness(1.02); }}
.it {{ font-family: "Cormorant", serif; font-style: italic; font-weight: 500; }}
"""


def photo(name):
    return f"file://{PHOTOS}/{name}"


# Pinault-style landscape: logo + small credits on top, two photos, big split headline at the bottom.
EXPO_PAYSAGE = (1600, 1200, f"""
<style>
.head {{ position: absolute; left: 70px; top: 62px; right: 70px; display: flex; align-items: flex-end; gap: 44px; }}
.head .logo {{ width: 520px; }}
.head .meta {{ font-size: 30px; line-height: 1.12; font-weight: 500; padding-bottom: 14px; }}
.head .meta b {{ font-weight: 400; }}
.p1 {{ position: absolute; left: 70px; top: 300px; width: 640px; height: 640px;
       background-image: url("{photo('chaleur_peignoir.webp')}"); background-position: 50% 30%; }}
.p2 {{ position: absolute; left: 760px; top: 300px; width: 770px; height: 640px;
       background-image: url("{photo('huile_mains.webp')}"); background-position: 50% 52%; }}
.big {{ position: absolute; font-weight: 600; font-size: 118px; letter-spacing: -0.02em; line-height: 1; }}
.b1 {{ left: 66px; top: 968px; }}
.b2 {{ right: 70px; top: 968px; }}
.sub {{ position: absolute; left: 70px; top: 1092px; font-size: 34px; }}
.foot {{ position: absolute; right: 70px; top: 1100px; font-size: 26px; letter-spacing: 0.14em; font-weight: 500; }}
</style>
<div class="head">
  <div class="logo">{LOGO}</div>
  <div class="meta">Rituel corps<br><b>Le parfum, autrement</b><br><b>En 4 étapes</b></div>
</div>
<div class="photo bw p1"></div>
<div class="photo p2"></div>
<div class="big b1">Sentir bon,</div>
<div class="big b2">sans parfum</div>
<div class="sub">L’eau · L’huile · Une signature · <span class="it" style="font-size:40px">la chaleur</span></div>
<div class="foot">@NESOLY.CARE</div>
""")

# Same family, portrait 120 x 176.
EXPO_PORTRAIT = (1200, 1760, f"""
<style>
.head {{ position: absolute; left: 64px; top: 60px; right: 64px; display: flex; align-items: flex-end; gap: 40px; }}
.head .logo {{ width: 560px; }}
.head .meta {{ font-size: 32px; line-height: 1.12; font-weight: 500; padding-bottom: 16px; }}
.head .meta b {{ font-weight: 400; }}
.p1 {{ position: absolute; left: 64px; right: 64px; top: 320px; height: 1080px;
       background-image: url("{photo('signature_creme.webp')}"); background-position: 50% 45%; }}
.big {{ position: absolute; font-weight: 600; font-size: 128px; letter-spacing: -0.02em; line-height: 1; }}
.b1 {{ left: 60px; top: 1440px; }}
.b2 {{ right: 64px; top: 1440px; }}
.sub {{ position: absolute; left: 64px; top: 1590px; font-size: 36px; }}
.foot {{ position: absolute; right: 64px; top: 1600px; font-size: 26px; letter-spacing: 0.14em; font-weight: 500; }}
</style>
<div class="head">
  <div class="logo">{LOGO}</div>
  <div class="meta">Rituel corps<br><b>Étape 03</b><br><b>Une signature</b></div>
</div>
<div class="photo bw p1"></div>
<div class="big b1">Rayonner</div>
<div class="big b2">sans crier</div>
<div class="sub">Sentir bon, <span class="it" style="font-size:44px">sans parfum</span></div>
<div class="foot">@NESOLY.CARE</div>
""")

# Product-ad style: full-bleed warm photo, centred logo, claim, brown tag and four step thumbnails.
RITUEL_PAYSAGE = (1600, 1200, f"""
<style>
.bg {{ position: absolute; inset: 0; background-image: url("{photo('huile_mains.webp')}");
       background-position: 50% 58%; }}
.veil {{ position: absolute; inset: 0;
         background: radial-gradient(ellipse 70% 60% at 50% 38%, rgba(62,46,49,.42), rgba(62,46,49,0) 75%),
                     linear-gradient(180deg, rgba(62,46,49,.35), rgba(62,46,49,0) 30%, rgba(62,46,49,0) 70%, rgba(62,46,49,.45)); }}
.logo {{ position: absolute; left: 50%; top: 70px; width: 470px; transform: translateX(-50%); color: var(--cream); }}
.tag {{ position: absolute; left: 50%; top: 255px; transform: translateX(-50%); color: var(--cream);
        font-size: 24px; letter-spacing: 0.42em; text-indent: 0.42em; font-weight: 400; }}
.claim {{ position: absolute; left: 0; right: 0; top: 420px; text-align: center; color: var(--cream); }}
.claim .num {{ font-family: "Cormorant", serif; font-style: italic; font-weight: 500; font-size: 190px; line-height: .9; }}
.claim .txt {{ font-size: 50px; font-weight: 500; letter-spacing: 0.04em; line-height: 1.2; margin-top: 12px; }}
.box {{ position: absolute; left: 70px; bottom: 120px; background: var(--brown); color: var(--cream);
        font-size: 40px; font-weight: 500; letter-spacing: 0.06em; line-height: 1.15; padding: 14px 24px; }}
.box + .box {{ bottom: 66px; background: var(--pink); color: var(--brown); font-size: 30px; padding: 10px 24px; }}
.legal {{ position: absolute; left: 70px; bottom: 26px; color: var(--cream); font-size: 17px; opacity: .9; }}
.steps {{ position: absolute; right: 60px; bottom: 50px; display: flex; gap: 10px; background: var(--cream);
          padding: 10px; border-radius: 6px; }}
.steps div {{ width: 118px; }}
.steps .photo {{ height: 150px; }}
.steps span {{ display: block; text-align: center; font-family: "Cormorant", serif; font-style: italic;
               font-size: 24px; padding-top: 4px; }}
</style>
<div class="photo bg"></div>
<div class="veil"></div>
<div class="logo">{LOGO}</div>
<div class="tag">RITUEL CORPS</div>
<div class="claim">
  <div class="num">6 à 10 h</div>
  <div class="txt">C’EST LA TENUE D’UN BON PARFUM.<br>INUTILE D’EN REMETTRE.</div>
</div>
<div class="box">LE RITUEL EN 4 ÉTAPES</div>
<div class="box">SENTIR BON, SANS PARFUM</div>
<div class="legal">Nettoyer sans parfum · Hydrater sur peau humide · Vaporiser deux pressions · Sublimer sur les vêtements</div>
<div class="steps">
  <div><div class="photo" style="background-image:url('{photo('eau_douche.webp')}');background-size:240%;background-position:52% 0"></div><span>L’eau</span></div>
  <div><div class="photo" style="background-image:url('{photo('huile_mains.webp')}');background-position:50% 50%"></div><span>L’huile</span></div>
  <div><div class="photo" style="background-image:url('{photo('signature_creme.webp')}');background-position:30% 20%"></div><span>Signature</span></div>
  <div><div class="photo" style="background-image:url('{photo('chaleur_peignoir.webp')}');background-position:50% 40%"></div><span>Chaleur</span></div>
</div>
""")

POSTERS = {
    "nesoly_affiche_expo_paysage": EXPO_PAYSAGE,
    "nesoly_affiche_expo_portrait": EXPO_PORTRAIT,
    "nesoly_affiche_rituel_paysage": RITUEL_PAYSAGE,
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
