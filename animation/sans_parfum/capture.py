"""Export nesoly_sans_parfum.html to an MP4 (or a few PNG previews) with headless Chromium.

Usage: python3 capture.py out.mp4            # full video, 30 fps
       python3 capture.py out_dir --preview  # PNG stills
"""
import os
import subprocess
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def main():
    out = sys.argv[1]
    preview = "--preview" in sys.argv
    with sync_playwright() as p:
        kw = {"executable_path": CHROMIUM} if os.path.exists(CHROMIUM) else {}
        browser = p.chromium.launch(**kw)
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto("file://" + os.path.join(HERE, "nesoly_sans_parfum.html") + "?capture")
        page.evaluate("window.NESOLY.ready")
        page.wait_for_timeout(500)
        if preview:
            os.makedirs(out, exist_ok=True)
            for t in [1.8, 4.0, 8, 12.9, 18, 27, 30, 36, 41.5, 44.5]:
                page.evaluate(f"window.NESOLY.render({t})")
                page.screenshot(path=os.path.join(out, f"t{t:05.1f}.png"))
            browser.close()
            return
        dur = page.evaluate("window.NESOLY.DURATION")
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS),
                               "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                               "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
        for i in range(int(dur * FPS) + 1):
            page.evaluate(f"window.NESOLY.render({i / FPS})")
            ff.stdin.write(page.screenshot(type="png"))
        ff.stdin.close()
        ff.wait()
        browser.close()


if __name__ == "__main__":
    main()
