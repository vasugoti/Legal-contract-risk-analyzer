"""Make a narrated, edited explainer video of the website.

Records the real site in a browser while a neural voice explains each feature.
Adds a title card, chapter labels, smooth zoom in/out, spotlights, subtitles
and an outro card. Output is a 1920x1080 MP4 plus matching .srt subtitles.

Setup (once):
    pip install playwright edge-tts imageio-ffmpeg
    python -m playwright install chromium

Run (start the app first, e.g. on http://127.0.0.1:8000):
    python scripts/make_demo_video.py
    python scripts/make_demo_video.py --voice en-IN-PrabhatNeural      # Indian English male
    python scripts/make_demo_video.py --voice en-US-AvaNeural          # US female
    python scripts/make_demo_video.py --url https://legal-contract-risk-analyzer.onrender.com

Output:
    docs/demo/demo-explainer.mp4
    docs/demo/demo-explainer.srt
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "demo"
LIVE_URL = "legal-contract-risk-analyzer.onrender.com"
W, H, SCALE = 1600, 900, 1.2          # CSS viewport x scale = 1920x1080 frames
FPS = 30
RESULT_TIMEOUT_MS = 240_000
VOICE_LEAD_IN = 0.35                   # seconds between scene start and voice


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        exe = shutil.which("ffmpeg")
        if not exe:
            sys.exit("ffmpeg not found. Run: pip install imageio-ffmpeg")
        return exe


FFMPEG = ffmpeg_exe()


def media_duration(path: Path) -> float:
    out = subprocess.run([FFMPEG, "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", out)
    if not m:
        raise RuntimeError(f"Could not read duration of {path}")
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


# ---------------------------------------------------------------------------
# In-page overlay: title cards, chapter label, subtitles, camera, spotlight
# ---------------------------------------------------------------------------
OVERLAY_JS = r"""
(() => {
  if (window.__demo) return;
  const css = `
  #__dm_root, #__dm_root * { box-sizing: border-box; }
  #__dm_card { position: fixed; inset: 0; z-index: 2147483600; display: flex; flex-direction: column;
    justify-content: center; align-items: flex-start; padding: 0 9vw; background: #2a1f18; color: #fbf7f1;
    opacity: 0; pointer-events: none; transition: opacity .8s cubic-bezier(.22,.61,.36,1); }
  #__dm_card.on { opacity: 1; }
  #__dm_card .eyebrow { font: 500 13px/1 var(--sans, sans-serif); letter-spacing: .28em; text-transform: uppercase;
    color: #d4a878; margin-bottom: 26px; transform: translateY(10px); opacity: 0; transition: all .9s .15s cubic-bezier(.22,.61,.36,1); }
  #__dm_card .title { font: 500 84px/1.02 var(--serif, serif); letter-spacing: -.02em; max-width: 14ch;
    transform: translateY(14px); opacity: 0; transition: all 1s .3s cubic-bezier(.22,.61,.36,1); }
  #__dm_card .title em { font-style: italic; color: #d4a878; }
  #__dm_card .sub { font: 300 22px/1.5 var(--sans, sans-serif); color: #e6dacb; margin-top: 26px; max-width: 46ch;
    transform: translateY(14px); opacity: 0; transition: all 1s .5s cubic-bezier(.22,.61,.36,1); }
  #__dm_card .rule { width: 0; height: 1px; background: #d4a878; margin-top: 40px; transition: width 1.4s .6s cubic-bezier(.22,.61,.36,1); }
  #__dm_card .meta { font: 500 13px/1 var(--sans, sans-serif); letter-spacing: .2em; text-transform: uppercase; color: #b9a58e;
    margin-top: 22px; opacity: 0; transition: opacity 1s .9s; }
  #__dm_card.on .eyebrow, #__dm_card.on .title, #__dm_card.on .sub { transform: none; opacity: 1; }
  #__dm_card.on .rule { width: 180px; }
  #__dm_card.on .meta { opacity: 1; }

  #__dm_chip { position: fixed; left: 40px; bottom: 132px; z-index: 2147483500; display: flex; align-items: baseline; gap: 12px;
    background: rgba(26, 19, 14, .86); color: #fbf7f1; padding: 10px 18px 11px; border-radius: 999px;
    border: 1px solid rgba(212, 168, 120, .35); backdrop-filter: blur(6px);
    opacity: 0; transform: translateY(8px); transition: all .6s cubic-bezier(.22,.61,.36,1); pointer-events: none; }
  #__dm_chip.on { opacity: 1; transform: none; }
  #__dm_chip .n { font: italic 500 18px/1 var(--serif, serif); color: #d4a878; }
  #__dm_chip .t { font: 500 12px/1 var(--sans, sans-serif); letter-spacing: .2em; text-transform: uppercase; }

  #__dm_cap { position: fixed; left: 50%; bottom: 40px; transform: translateX(-50%) translateY(6px); z-index: 2147483500;
    max-width: 1080px; width: max-content; text-align: center; padding: 13px 26px 14px; border-radius: 12px;
    background: rgba(20, 14, 10, .82); color: #fbf7f1; font: 400 23px/1.45 var(--sans, sans-serif); letter-spacing: .005em;
    opacity: 0; transition: opacity .35s ease, transform .35s ease; pointer-events: none; box-shadow: 0 12px 40px -12px rgba(0,0,0,.5); }
  #__dm_cap.on { opacity: 1; transform: translateX(-50%); }

  #__dm_spot { position: fixed; z-index: 2147483400; border-radius: 12px; pointer-events: none;
    border: 2px solid #d4a878; box-shadow: 0 0 0 9999px rgba(15, 10, 7, .42), 0 0 30px 4px rgba(212,168,120,.35);
    opacity: 0; transition: opacity .5s ease, left .7s cubic-bezier(.22,.61,.36,1), top .7s cubic-bezier(.22,.61,.36,1),
      width .7s cubic-bezier(.22,.61,.36,1), height .7s cubic-bezier(.22,.61,.36,1); }
  #__dm_spot.on { opacity: 1; }

  #__dm_cursor { position: fixed; left: 0; top: 0; width: 20px; height: 20px; margin: -10px 0 0 -10px; border-radius: 50%;
    background: rgba(212,168,120,.35); border: 2px solid rgba(212,168,120,.95); z-index: 2147483550; pointer-events: none;
    transition: transform .15s ease, background .15s ease; }
  body.__dm_cam { transition: transform 1.1s cubic-bezier(.65,0,.35,1); transform-origin: 0 0; will-change: transform; }
  body.__dm_cam .topbar { transition: opacity .45s ease; }
  html.__dm_zoomed body.__dm_cam .topbar { opacity: 0; }
  `;
  const style = document.createElement('style'); style.textContent = css; document.documentElement.appendChild(style);
  const root = document.createElement('div'); root.id = '__dm_root'; document.documentElement.appendChild(root);
  root.innerHTML = `<div id="__dm_card"></div><div id="__dm_chip"><span class="n"></span><span class="t"></span></div>
    <div id="__dm_cap"></div><div id="__dm_spot"></div><div id="__dm_cursor"></div>`;
  const $ = id => document.getElementById(id);
  document.addEventListener('mousemove', e => { const c = $('__dm_cursor'); c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
  document.addEventListener('mousedown', () => { const c = $('__dm_cursor'); c.style.transform = 'scale(.7)'; c.style.background = 'rgba(212,168,120,.7)'; }, true);
  document.addEventListener('mouseup', () => { const c = $('__dm_cursor'); c.style.transform = ''; c.style.background = ''; }, true);
  document.body.classList.add('__dm_cam');
  let capTimers = [];

  window.__demo = {
    card(html) { const c = $('__dm_card'); c.innerHTML = html; void c.offsetWidth; c.classList.add('on'); },
    cardOff() { $('__dm_card').classList.remove('on'); },
    chip(n, t) { const c = $('__dm_chip'); c.querySelector('.n').textContent = n; c.querySelector('.t').textContent = t; c.classList.add('on'); },
    chipOff() { $('__dm_chip').classList.remove('on'); },
    captions(chunks) {           // chunks: [[startSec, endSec, text], ...]
      capTimers.forEach(clearTimeout); capTimers = [];
      const cap = $('__dm_cap');
      chunks.forEach(([s, e, t]) => {
        capTimers.push(setTimeout(() => { cap.textContent = t; cap.classList.add('on'); }, s * 1000));
        capTimers.push(setTimeout(() => cap.classList.remove('on'), e * 1000));
      });
    },
    zoom(sel, scale) {           // smooth camera move to centre an element
      const el = document.querySelector(sel); if (!el) return;
      const b = document.body; const prev = b.style.transform; b.style.transition = 'none'; b.style.transform = 'none';
      const r = el.getBoundingClientRect(); b.style.transform = prev; void b.offsetWidth; b.style.transition = '';
      const px = r.left + r.width / 2 + window.scrollX, py = r.top + r.height / 2 + window.scrollY;
      const tx = window.scrollX + innerWidth / 2 - px * scale, ty = window.scrollY + innerHeight / 2 - py * scale;
      document.documentElement.classList.add('__dm_zoomed');
      clearTimeout(window.__dm_zt);
      b.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
    },
    zoomOut() {
      document.body.style.transform = 'none';
      clearTimeout(window.__dm_zt);
      window.__dm_zt = setTimeout(() => document.documentElement.classList.remove('__dm_zoomed'), 1100);
    },
    spot(sel, pad = 10) {
      const el = document.querySelector(sel); const s = $('__dm_spot'); if (!el) return;
      const r = el.getBoundingClientRect();
      Object.assign(s.style, { left: (r.left - pad) + 'px', top: (r.top - pad) + 'px', width: (r.width + pad * 2) + 'px', height: (r.height + pad * 2) + 'px' });
      s.classList.add('on');
    },
    spotOff() { $('__dm_spot').classList.remove('on'); },
  };
})();
"""


# ---------------------------------------------------------------------------
# Script
# ---------------------------------------------------------------------------
@dataclass
class Scene:
    chapter: str | None          # e.g. "01 · Upload"; None for cards
    text: str                    # narration
    action: Callable[[Page], None]
    min_seconds: float = 0.0


def glide(page: Page, sel: str, steps: int = 28) -> None:
    box = page.locator(sel).first.bounding_box()
    if box:
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=steps)


def click(page: Page, sel: str, pause: int = 300) -> None:
    glide(page, sel)
    page.wait_for_timeout(pause)
    page.locator(sel).first.click()


def scroll_to(page: Page, sel: str, offset: int = 90, ms: int = 1100) -> None:
    page.evaluate(
        """([sel, off, dur]) => new Promise(res => {
          const el = document.querySelector(sel); if (!el) return res();
          const a = scrollY, b = el.getBoundingClientRect().top + scrollY - off, t0 = performance.now();
          const f = t => { const p = Math.min(1, (t - t0) / dur), e = p < .5 ? 4*p*p*p : 1 - Math.pow(-2*p + 2, 3) / 2;
            scrollTo(0, a + (b - a) * e); p < 1 ? requestAnimationFrame(f) : res(); };
          requestAnimationFrame(f); })""",
        [sel, offset, ms],
    )


def demo(page: Page, call: str, *args) -> None:
    page.evaluate(f"(a) => window.__demo.{call}(...a)", list(args))


TITLE_CARD = """<div class="eyebrow">Final-year B.Tech NLP project</div>
<div class="title">Contract <em>Risk</em> Analyzer</div>
<div class="sub">Read the fine print, before you sign.</div><div class="rule"></div>
<div class="meta">RoBERTa &nbsp;·&nbsp; LexGLUE LEDGAR &nbsp;·&nbsp; FastAPI</div>"""

OUTRO_CARD = f"""<div class="eyebrow">Try it yourself</div>
<div class="title">Read the fine print, <em>before</em> you sign.</div>
<div class="sub">{LIVE_URL}</div><div class="rule"></div>
<div class="meta">Automated risk triage &nbsp;·&nbsp; Not legal advice</div>"""


def s_title(p: Page) -> None:
    demo(p, "card", TITLE_CARD)


def s_home(p: Page) -> None:
    demo(p, "cardOff")
    p.wait_for_timeout(900)
    p.mouse.move(800, 420, steps=20)
    p.wait_for_timeout(1500)
    demo(p, "spot", "#dropzone", 12)
    p.wait_for_timeout(2600)
    demo(p, "spotOff")
    click(p, "#btn-load-sample-doc")
    p.wait_for_timeout(700)
    click(p, "[data-sample=high]")
    p.wait_for_timeout(900)


def s_analyse(p: Page) -> None:
    demo(p, "spot", "#btn-analyze-doc", 8)
    p.wait_for_timeout(1200)
    demo(p, "spotOff")
    click(p, "#btn-analyze-doc")
    p.wait_for_selector("#doc-results-content:not([hidden])", timeout=RESULT_TIMEOUT_MS)
    p.wait_for_timeout(600)
    scroll_to(p, "#doc-results-content")
    p.wait_for_timeout(1200)


def s_score(p: Page) -> None:
    p.mouse.move(1560, 860, steps=15)
    demo(p, "zoom", ".verdict-main", 1.45)
    p.wait_for_timeout(5200)
    demo(p, "zoomOut")
    p.wait_for_timeout(1300)
    demo(p, "spot", ".figures", 6)
    p.wait_for_timeout(2600)
    demo(p, "spotOff")


def s_risks(p: Page) -> None:
    scroll_to(p, "#top-risks-card", offset=110)
    p.wait_for_timeout(1000)
    demo(p, "zoom", "#top-risks", 1.25)
    p.wait_for_timeout(4200)
    demo(p, "zoomOut")
    p.wait_for_timeout(1100)


def s_findings(p: Page) -> None:
    scroll_to(p, "#severity-filter", offset=170)
    p.wait_for_timeout(700)
    click(p, "#severity-filter [data-sev=critical]")
    p.wait_for_timeout(900)
    first = p.locator("#flags-table-body details").first
    if first.count() and first.get_attribute("open") is None:
        glide(p, "#flags-table-body details:first-child summary")
        first.locator("summary").click()
    p.wait_for_timeout(900)
    p.mouse.move(1560, 860, steps=15)
    demo(p, "zoom", "#flags-table-body details:first-child", 1.35)
    p.wait_for_timeout(5600)
    demo(p, "zoomOut")
    p.wait_for_timeout(1100)
    click(p, "#severity-filter [data-sev=all]")
    p.wait_for_timeout(600)


def s_download(p: Page) -> None:
    scroll_to(p, "#doc-results-content", offset=90)
    p.wait_for_timeout(900)
    click(p, "#btn-download-report")
    p.wait_for_timeout(700)
    demo(p, "spot", "#download-menu", 6)
    p.wait_for_timeout(3600)
    demo(p, "spotOff")
    p.keyboard.press("Escape")
    p.mouse.click(1500, 820)
    p.wait_for_timeout(500)


def s_clause(p: Page) -> None:
    p.evaluate("scrollTo({top: 0, behavior: 'smooth'})")
    p.wait_for_timeout(800)
    click(p, "#tabbtn-clause")
    p.wait_for_timeout(900)
    click(p, "#preset-liab")
    p.wait_for_selector("#clause-result-card:not([hidden])", timeout=RESULT_TIMEOUT_MS)
    p.wait_for_timeout(1000)
    p.mouse.move(1560, 860, steps=15)
    demo(p, "zoom", "#clause-result-card .prediction", 1.5)
    p.wait_for_timeout(3600)
    demo(p, "zoomOut")
    p.wait_for_timeout(1000)
    demo(p, "spot", "#clause-topk-body", 10)
    p.wait_for_timeout(2400)
    demo(p, "spotOff")


def s_model(p: Page) -> None:
    click(p, "#tabbtn-metrics")
    p.wait_for_timeout(1800)
    scroll_to(p, "#benchmark-card", offset=110)
    p.wait_for_timeout(2600)


def s_outro(p: Page) -> None:
    demo(p, "chipOff")
    demo(p, "card", OUTRO_CARD)


SCENES = [
    Scene(None, "Contracts are long, dense, and easy to sign without reading. "
                "Contract Risk Analyzer reads the fine print for you.", s_title, 5.5),
    Scene("01 · Upload", "Start by uploading a PDF or Word file, or simply paste the text. "
                         "Let's try a one-sided vendor contract.", s_home, 9),
    Scene("02 · Analyse", "With one click, the contract is split into clauses, and a fine-tuned RoBERTa model "
                          "classifies every clause into one of one hundred LEDGAR categories.", s_analyse),
    Scene("03 · Verdict", "The verdict comes first: a single risk score from zero to one hundred, a risk level, "
                          "and a clear course of action. Each type of risk counts once, so a long contract "
                          "is never penalised just for being long.", s_score),
    Scene("04 · Principal risks", "Below it, the principal risks are grouped by type and ordered by severity.", s_risks),
    Scene("05 · Findings", "Every finding is explainable. You see the exact clause, the risky phrase highlighted, "
                           "why it matters, and a practical recommendation to fix it.", s_findings),
    Scene("06 · Report", "The complete analysis can be downloaded as a print-ready PDF, a Word document, "
                         "a web page, or raw JSON.", s_download),
    Scene("07 · Single clause", "You can also test a single clause. The model shows its predicted category, "
                                "its confidence, and the other categories it considered.", s_clause),
    Scene("08 · Model", "And the model tab reports live usage, with honest benchmark results "
                        "on the LexGLUE LEDGAR test set.", s_model),
    Scene(None, "Contract Risk Analyzer. Read the fine print, before you sign. "
                "Try it free at legal contract risk analyzer dot onrender dot com.", s_outro, 7),
]


# ---------------------------------------------------------------------------
# Voice
# ---------------------------------------------------------------------------
async def _tts(text: str, voice: str, rate: str, out: Path) -> None:
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(out))


def make_voice(tmp: Path, voice: str, rate: str, no_voice: bool) -> list[tuple[Path | None, float]]:
    result = []
    for i, sc in enumerate(SCENES):
        if no_voice:
            result.append((None, max(2.0, len(sc.text.split()) / 2.6)))
            continue
        out = tmp / f"vo_{i:02d}.mp3"
        for attempt in range(3):
            try:
                asyncio.run(_tts(sc.text, voice, rate, out))
                break
            except Exception as exc:  # network hiccup
                if attempt == 2:
                    sys.exit(f"Voice generation failed: {exc}\nCheck internet, or run with --no-voice.")
                time.sleep(2)
        result.append((out, media_duration(out)))
        print(f"  voice {i + 1}/{len(SCENES)}: {result[-1][1]:.1f}s")
    return result


def caption_chunks(text: str, duration: float, max_words: int = 13) -> list[list]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    parts: list[str] = []
    for s in sentences:
        words = s.split()
        while len(words) > max_words:
            cut = max_words
            for k in range(max_words, max_words // 2, -1):   # break after a comma if possible
                if words[k - 1].endswith(","):
                    cut = k
                    break
            parts.append(" ".join(words[:cut]))
            words = words[cut:]
        if words:
            parts.append(" ".join(words))
    total = sum(len(p) for p in parts) or 1
    t, chunks = VOICE_LEAD_IN, []
    for p in parts:
        d = duration * len(p) / total
        chunks.append([round(t, 2), round(t + d - 0.05, 2), p])
        t += d
    return chunks


# ---------------------------------------------------------------------------
# Recording (CDP screencast -> sharp JPEG frames with timestamps)
# ---------------------------------------------------------------------------
def wait_awake(url: str) -> None:
    deadline = time.time() + 300
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=30) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(4)
    sys.exit(f"{url} is not responding. Start the app first.")


def record(url: str, voices, tmp: Path, extra_css: str | None, browser_args: dict):
    frames_dir = tmp / "frames"
    frames_dir.mkdir()
    frames: list[tuple[float, Path]] = []
    marks: list[float] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(**browser_args)
        ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=SCALE)
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle")
        if extra_css:
            page.add_style_tag(content=extra_css)
        page.evaluate("document.fonts.ready")
        page.evaluate(OVERLAY_JS)
        page.mouse.move(W - 40, H - 40)

        # warm-up so the first real analysis is fast
        try:
            page.evaluate("""fetch('/analyze/clause', {method: 'POST', headers: {'Content-Type': 'application/json'},
                             body: JSON.stringify({text: 'This Agreement is governed by the laws of India.'})})""")
        except Exception:
            pass

        cdp = ctx.new_cdp_session(page)

        def on_frame(ev):
            idx = len(frames)
            path = frames_dir / f"f{idx:06d}.jpg"
            path.write_bytes(base64.b64decode(ev["data"]))
            frames.append((ev["metadata"]["timestamp"], path))
            try:
                cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
            except Exception:
                pass

        cdp.on("Page.screencastFrame", on_frame)
        cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92,
                                          "maxWidth": int(W * SCALE), "maxHeight": int(H * SCALE), "everyNthFrame": 1})
        page.wait_for_timeout(400)
        # a tiny mouse movement guarantees an initial frame
        page.mouse.move(W - 41, H - 41)
        page.wait_for_timeout(200)

        for i, (sc, (_, dur)) in enumerate(zip(SCENES, voices)):
            start = time.time()
            marks.append(start)
            if sc.chapter:
                n, t = sc.chapter.split(" · ", 1)
                demo(page, "chip", n, t)
            demo(page, "captions", caption_chunks(sc.text, dur))
            sc.action(page)
            target = max(dur + VOICE_LEAD_IN + 0.6, sc.min_seconds)
            remaining = target - (time.time() - start)
            if remaining > 0:
                page.wait_for_timeout(int(remaining * 1000))
            print(f"  scene {i + 1}/{len(SCENES)} recorded ({time.time() - start:.1f}s)")
        page.wait_for_timeout(1200)
        end = time.time()
        cdp.send("Page.stopScreencast")
        page.wait_for_timeout(300)
        ctx.close()
        browser.close()
    return frames, marks, end


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------
def assemble(frames, marks, end, voices, tmp: Path, out: Path) -> None:
    if len(frames) < 2:
        sys.exit("No frames were captured.")
    t0 = frames[0][0]
    if abs(t0 - marks[0]) > 30:  # screencast clock is not wall-clock: align on first frame
        sys.exit("Frame timestamps are not wall-clock; cannot sync audio.")
    concat = tmp / "frames.txt"
    with concat.open("w", encoding="utf-8") as f:
        f.write("ffconcat version 1.0\n")
        for (ts, path), nxt in zip(frames, frames[1:] + [(end, None)]):
            f.write(f"file '{path.as_posix()}'\nduration {max(nxt[0] - ts, 0.001):.4f}\n")
        f.write(f"file '{frames[-1][1].as_posix()}'\n")
    video = tmp / "video.mp4"
    vtmp = tmp / "video.part.mp4"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat),
                    "-vf", f"fps={FPS},scale=1920:1080:flags=lanczos,format=yuv420p",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(vtmp)], check=True)
    vtmp.rename(video)
    total = media_duration(video)

    clips = [(path, mark - t0 + VOICE_LEAD_IN) for (path, _), mark in zip(voices, marks) if path]
    out_tmp = out.with_name(out.stem + ".part.mp4")
    if clips:
        cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", str(video)]
        for path, _ in clips:
            cmd += ["-i", str(path)]
        parts = [f"[{i + 1}:a]aresample=48000,adelay={int(max(0, at) * 1000)}:all=1[a{i}]" for i, (_, at) in enumerate(clips)]
        mix = "".join(f"[a{i}]" for i in range(len(clips)))
        fc = ";".join(parts) + f";{mix}amix=inputs={len(clips)}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,apad[aout]"
        cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[aout]", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out_tmp)]
    else:
        cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", str(video), "-c:v", "copy", "-movflags", "+faststart", str(out_tmp)]
    subprocess.run(cmd, check=True)
    out_tmp.replace(out)

    # subtitles
    srt, n = [], 1
    for sc, (_, dur), mark in zip(SCENES, voices, marks):
        base = mark - t0
        for s, e, text in caption_chunks(sc.text, dur):
            srt.append(f"{n}\n{_ts(base + s)} --> {_ts(base + e)}\n{text}\n")
            n += 1
    out.with_suffix(".srt").write_text("\n".join(srt), encoding="utf-8")
    print(f"Saved {out} ({total:.0f}s, {out.stat().st_size / 1e6:.1f} MB) and {out.with_suffix('.srt').name}")


def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8000", help="running app (local is faster than Render)")
    ap.add_argument("--voice", default="en-US-AndrewNeural",
                    help="edge-tts voice, e.g. en-US-AndrewNeural, en-US-AvaNeural, en-IN-PrabhatNeural, en-IN-NeerjaNeural")
    ap.add_argument("--rate", default="-4%", help="speaking speed, e.g. -10%%, +0%%")
    ap.add_argument("--out", default=str(OUT_DIR / "demo-explainer.mp4"))
    ap.add_argument("--no-voice", action="store_true", help="subtitles only (no internet needed)")
    ap.add_argument("--css", help=argparse.SUPPRESS)
    ap.add_argument("--chrome", help=argparse.SUPPRESS)
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    browser_args = {"executable_path": args.chrome, "args": ["--no-sandbox"]} if args.chrome else {}
    url = args.url.rstrip("/")
    print(f"Checking {url} ...")
    wait_awake(url)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        print("Generating voice-over..." if not args.no_voice else "No voice: timing from text length.")
        voices = make_voice(tmp, args.voice, args.rate, args.no_voice)
        print("Recording the site...")
        frames, marks, end = record(url, voices, tmp, args.css, browser_args)
        print(f"Assembling video from {len(frames)} frames...")
        assemble(frames, marks, end, voices, tmp, out)


if __name__ == "__main__":
    main()
