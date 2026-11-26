"""Capture README screenshots and a demo video from the running website.

Usage (from the project root):
    pip install playwright imageio-ffmpeg
    python -m playwright install chromium
    python scripts/capture_readme_media.py
    python scripts/capture_readme_media.py --url http://127.0.0.1:8000   # local server

Outputs:
    docs/images/01-home.png ... 07-mobile.png
    docs/demo/demo.mp4  (H.264, plays on GitHub)
    docs/demo/demo.gif  (short loop shown inline in the README)
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

DEFAULT_URL = "https://legal-contract-risk-analyzer.onrender.com"
ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "docs" / "images"
DEMO_DIR = ROOT / "docs" / "demo"
RESULT_TIMEOUT_MS = 240_000  # Render free tier can be slow on the first request

# A visible cursor for the demo video (headless browsers don't draw one).
CURSOR_JS = """
(() => {
  const add = () => {
    if (document.getElementById('__demo_cursor')) return;
    const c = document.createElement('div');
    c.id = '__demo_cursor';
    c.style.cssText = 'position:fixed;left:0;top:0;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;' +
      'background:rgba(139,106,72,.35);border:2px solid rgba(139,106,72,.9);z-index:2147483647;pointer-events:none;' +
      'transition:transform .15s ease, background .15s ease;';
    document.body.appendChild(c);
    document.addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
    document.addEventListener('mousedown', () => { c.style.transform = 'scale(.7)'; c.style.background = 'rgba(139,106,72,.6)'; }, true);
    document.addEventListener('mouseup', () => { c.style.transform = 'scale(1)'; c.style.background = 'rgba(139,106,72,.35)'; }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', add); else add();
})();
"""


def wait_until_awake(url: str, timeout_s: int = 300) -> None:
    """Render's free plan sleeps after 15 minutes; poll /health until it answers."""
    print(f"Waking up {url} (can take ~1 minute on Render free tier)...")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=30) as r:
                if r.status == 200:
                    print("  site is awake")
                    return
        except Exception:
            pass
        time.sleep(5)
    sys.exit(f"Site did not respond at {url}/health within {timeout_s}s")


def glide(page: Page, selector: str, steps: int = 25) -> None:
    """Move the mouse smoothly to an element (for the video)."""
    box = page.locator(selector).first.bounding_box()
    if box:
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=steps)


def click(page: Page, selector: str, pause: int = 350) -> None:
    glide(page, selector)
    page.wait_for_timeout(pause)
    page.locator(selector).first.click()


def smooth_scroll_to(page: Page, selector: str, offset: int = 90, duration_ms: int = 900) -> None:
    page.evaluate(
        """([sel, off, dur]) => new Promise(res => {
            const el = document.querySelector(sel); if (!el) return res();
            const start = window.scrollY, end = el.getBoundingClientRect().top + window.scrollY - off;
            const t0 = performance.now();
            const step = t => { const p = Math.min(1, (t - t0) / dur), e = p < .5 ? 2*p*p : 1 - Math.pow(-2*p + 2, 2) / 2;
              window.scrollTo(0, start + (end - start) * e); p < 1 ? requestAnimationFrame(step) : res(); };
            requestAnimationFrame(step); })""",
        [selector, offset, duration_ms],
    )


def run_analysis(page: Page, sample: str = "high") -> None:
    click(page, "#btn-load-sample-doc")
    page.wait_for_timeout(500)
    click(page, f"[data-sample={sample}]")
    page.wait_for_timeout(700)
    click(page, "#btn-analyze-doc")
    page.wait_for_selector("#doc-results-content:not([hidden])", timeout=RESULT_TIMEOUT_MS)
    page.wait_for_timeout(1600)  # let the score count up


def screenshots(pw, url: str, extra_css: str | None) -> None:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)
    page = ctx.new_page()
    page.goto(url, wait_until="networkidle")
    if extra_css:
        page.add_style_tag(content=extra_css)
    page.wait_for_timeout(1200)
    page.screenshot(path=IMG_DIR / "01-home.png")
    print("  01-home.png")

    run_analysis(page)
    smooth_scroll_to(page, "#doc-results-content", duration_ms=10)
    page.mouse.move(5, 5)
    page.wait_for_timeout(600)
    page.screenshot(path=IMG_DIR / "02-risk-report.png")
    print("  02-risk-report.png")

    smooth_scroll_to(page, "#severity-filter", offset=150, duration_ms=10)
    page.wait_for_timeout(300)
    first = page.locator("#flags-table-body details").first
    if first.count() and first.get_attribute("open") is None:
        first.locator("summary").click()
    page.mouse.move(5, 5)
    page.wait_for_timeout(600)
    page.screenshot(path=IMG_DIR / "03-findings.png")
    print("  03-findings.png")

    smooth_scroll_to(page, "#doc-results-content", duration_ms=10)
    page.wait_for_timeout(300)
    page.locator("#btn-download-report").click()
    page.wait_for_timeout(600)
    page.screenshot(path=IMG_DIR / "04-download-report.png")
    print("  04-download-report.png")
    page.keyboard.press("Escape")
    page.mouse.click(5, 450)

    page.locator("#tabbtn-clause").click()
    page.locator("#preset-indem").click()
    page.wait_for_selector("#clause-result-card:not([hidden])", timeout=RESULT_TIMEOUT_MS)
    page.wait_for_timeout(1200)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=IMG_DIR / "05-single-clause.png")
    print("  05-single-clause.png")

    page.locator("#tabbtn-metrics").click()
    page.wait_for_timeout(2500)
    page.screenshot(path=IMG_DIR / "06-model.png")
    print("  06-model.png")
    ctx.close()

    mctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    m = mctx.new_page()
    m.goto(url, wait_until="networkidle")
    if extra_css:
        m.add_style_tag(content=extra_css)
    m.wait_for_timeout(1000)
    m.locator("#btn-load-sample-doc").click()
    m.locator("[data-sample=medium]").click()
    m.locator("#btn-analyze-doc").click()
    m.wait_for_selector("#doc-results-content:not([hidden])", timeout=RESULT_TIMEOUT_MS)
    m.wait_for_timeout(1500)
    m.evaluate("document.querySelector('#doc-results-content').scrollIntoView()")
    m.wait_for_timeout(500)
    m.screenshot(path=IMG_DIR / "07-mobile.png")
    print("  07-mobile.png")
    mctx.close()
    browser.close()


def demo_video(pw, url: str, extra_css: str | None) -> Path:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DEMO_DIR / "_raw"
    shutil.rmtree(tmp, ignore_errors=True)
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1280, "height": 800},
                              record_video_dir=str(tmp), record_video_size={"width": 1280, "height": 800})
    ctx.add_init_script(CURSOR_JS)
    page = ctx.new_page()
    page.goto(url, wait_until="networkidle")
    if extra_css:
        page.add_style_tag(content=extra_css)
    page.mouse.move(640, 300)
    page.wait_for_timeout(1800)

    run_analysis(page, "high")
    smooth_scroll_to(page, "#doc-results-content", duration_ms=1200)
    page.wait_for_timeout(2200)
    smooth_scroll_to(page, "#top-risks-card", duration_ms=1200)
    page.wait_for_timeout(1800)
    smooth_scroll_to(page, "#severity-filter", offset=160, duration_ms=1000)
    page.wait_for_timeout(600)
    click(page, "#severity-filter [data-sev=critical]")
    page.wait_for_timeout(900)
    flags = page.locator("#flags-table-body details")
    if flags.count() > 0:
        glide(page, "#flags-table-body details:first-child summary")
        page.wait_for_timeout(300)
        if not flags.first.get_attribute("open"):
            flags.first.locator("summary").click()
    page.wait_for_timeout(2600)
    click(page, "#severity-filter [data-sev=all]")
    page.wait_for_timeout(600)
    smooth_scroll_to(page, "#doc-results-content", duration_ms=1200)
    page.wait_for_timeout(700)
    click(page, "#btn-download-report")
    page.wait_for_timeout(1800)
    page.keyboard.press("Escape")
    page.mouse.click(1200, 700)
    page.wait_for_timeout(400)
    page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    page.wait_for_timeout(900)
    click(page, "#tabbtn-clause")
    page.wait_for_timeout(700)
    click(page, "#preset-liab")
    page.wait_for_selector("#clause-result-card:not([hidden])", timeout=RESULT_TIMEOUT_MS)
    page.wait_for_timeout(2600)
    click(page, "#tabbtn-metrics")
    page.wait_for_timeout(2800)

    video = page.video
    ctx.close()
    browser.close()
    raw = Path(video.path())
    return raw


def convert(raw: Path) -> None:
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        dest = DEMO_DIR / "demo.webm"
        shutil.move(str(raw), dest)
        print(f"  ffmpeg not found — kept {dest.name} (install imageio-ffmpeg for mp4/gif)")
        return
    mp4, gif = DEMO_DIR / "demo.mp4", DEMO_DIR / "demo.gif"
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(raw), "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)], check=True)
    vf = "fps=8,scale=820:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(raw), "-vf", vf, "-loop", "0", str(gif)], check=True)
    shutil.rmtree(raw.parent, ignore_errors=True)
    print(f"  {mp4.name} ({mp4.stat().st_size / 1e6:.1f} MB), {gif.name} ({gif.stat().st_size / 1e6:.1f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--skip-video", action="store_true")
    ap.add_argument("--css", help=argparse.SUPPRESS)  # internal: extra CSS for offline previews
    args = ap.parse_args()
    url = args.url.rstrip("/")
    wait_until_awake(url)
    with sync_playwright() as pw:
        print("Capturing screenshots...")
        screenshots(pw, url, args.css)
        if not args.skip_video:
            print("Recording demo video...")
            convert(demo_video(pw, url, args.css))
    print("Done.")


if __name__ == "__main__":
    main()
