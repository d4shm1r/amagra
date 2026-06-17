"""Frame the raw dashboard screenshots in a browser-window mockup.

Reads docs/screenshots/raw/{name}.png and writes the framed, presentation-ready
docs/screenshots/{name}.png referenced by the README: rounded window, cream
title bar with gold traffic-lights + an address pill, a soft warm shadow, on a
cream→gold gradient backdrop. Idempotent — always reads from raw/.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = "/home/dashmir/agentic-ai/docs/screenshots"
RAW = os.path.join(ROOT, "raw")
GOLD = [(0xC4, 0x88, 0x08), (0xDE, 0xB8, 0x38), (0x9A, 0x6C, 0x00)]
FONT_PATH = "/home/dashmir/agentic-ai/ui/scripts/fonts/DMSans-ExtraBold.ttf"

def frame(name):
    src = Image.open(os.path.join(RAW, f"{name}.png")).convert("RGBA")
    W, H = src.size
    rad = 16
    bar_h = 66
    win_w, win_h = W, H + bar_h

    win = Image.new("RGBA", (win_w, win_h), (0, 0, 0, 0))
    # title bar (cream), rounded top only
    bar = Image.new("RGBA", (win_w, bar_h + rad), (244, 240, 232, 255))
    bm = Image.new("L", (win_w, bar_h + rad), 0)
    ImageDraw.Draw(bm).rounded_rectangle([0, 0, win_w - 1, bar_h + rad], radius=rad, fill=255)
    win.paste(bar, (0, 0), bm)
    d = ImageDraw.Draw(win)
    for i, c in enumerate(GOLD):
        d.ellipse([30 + i * 28, bar_h // 2 - 8, 30 + i * 28 + 16, bar_h // 2 + 8], fill=c + (255,))
    # address pill
    try:
        font = ImageFont.truetype(FONT_PATH, 22)
    except Exception:
        font = ImageFont.load_default()
    d.rounded_rectangle([150, bar_h // 2 - 17, win_w - 150, bar_h // 2 + 17],
                        radius=17, fill=(255, 255, 255, 255), outline=(0xE0, 0xD6, 0xC4, 255))
    label = "amagra  ·  localhost:3000"
    tw = d.textbbox((0, 0), label, font=font)[2]
    d.text(((win_w - tw) // 2, bar_h // 2 - 13), label, fill=(0x8A, 0x70, 0x40, 255), font=font)

    # screenshot under the bar — square top, rounded bottom
    sm = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sm).rounded_rectangle([0, -rad, W - 1, H - 1], radius=rad, fill=255)
    sq = src.copy(); sq.putalpha(sm)
    win.paste(sq, (0, bar_h), sq)

    # gradient backdrop
    pad = 120
    bw, bh = win_w + pad * 2, win_h + pad * 2
    top, bot = np.array([0xF4, 0xEE, 0xE4]), np.array([0xEC, 0xDF, 0xC2])
    f = (np.arange(bh) / (bh - 1))[:, None]
    col = (top * (1 - f) + bot * f).astype(np.uint8)
    bg = Image.fromarray(
        np.dstack([np.repeat(col[:, None, :], bw, axis=1), np.full((bh, bw), 255, np.uint8)]), "RGBA")
    # soft warm shadow
    sh = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        [pad + 10, pad + 24, pad + win_w + 10, pad + win_h + 24], radius=rad + 4, fill=(120, 86, 20, 95))
    bg.alpha_composite(sh.filter(ImageFilter.GaussianBlur(30)))
    bg.alpha_composite(win, (pad, pad))
    out = os.path.join(ROOT, f"{name}.png")
    bg.convert("RGB").save(out)
    print(f"framed {name}: {bg.size} -> {out}")

if __name__ == "__main__":
    for n in ("chat", "library", "inspect"):
        frame(n)
