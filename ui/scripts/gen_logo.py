"""Render the Amagra README lockup: open gold "A" mark + AMAGRA wordmark.

Transparent background, single continuous 135deg gold sheen across mark + text
so it reads on GitHub's light and dark themes. Drawn at 3x then downscaled.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = "/home/dashmir/agentic-ai/docs/amagra-logo.png"
SS = 3

STOPS = [
    (0.00, (0xFF, 0xE8, 0x80)),
    (0.30, (0xDE, 0xB8, 0x38)),
    (0.58, (0xC4, 0x88, 0x08)),
    (0.82, (0x9A, 0x6C, 0x00)),
    (1.00, (0x6C, 0x4C, 0x00)),
]

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf",
    "/usr/share/fonts/opentype/inter/Inter-Black.otf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

def find_font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return ImageFont.truetype(p, size), p
    raise SystemExit("no usable font found")

def gold_lut():
    lut = []
    for i in range(256):
        t = i / 255.0
        for j in range(len(STOPS) - 1):
            p0, c0 = STOPS[j]; p1, c1 = STOPS[j + 1]
            if t <= p1:
                f = 0 if p1 == p0 else (t - p0) / (p1 - p0)
                lut.append([int(round(c0[k] + (c1[k] - c0[k]) * f)) for k in range(3)])
                break
        else:
            lut.append(list(STOPS[-1][1]))
    return np.array(lut, dtype=np.uint8)

def thick(draw, p0, p1, w, fill=255):
    draw.line([p0, p1], fill=fill, width=w)
    r = w // 2
    for (x, y) in (p0, p1):
        draw.ellipse([x - r, y - r, x + r, y + r], fill=fill)

def draw_tracked_text(draw, xy, text, font, tracking, fill=255):
    """Draw text with per-character letter-spacing; return total advance width."""
    x, y = xy
    start = x
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        w = draw.textbbox((0, 0), ch, font=font)[2]
        x += w + tracking
    return x - tracking - start

# ── layout (3x space) ────────────────────────────────────────────────
H = 300 * SS                       # canvas height
mark_h = 210 * SS                  # A mark height
pad = 24 * SS
gap = 40 * SS
font_px = 200 * SS
tracking = 6 * SS
font, font_path = find_font(font_px)

# measure wordmark on a scratch image
scratch = Image.new("L", (10, 10))
sd = ImageDraw.Draw(scratch)
text = "AMAGRA"
text_w = 0
for ch in text:
    text_w += sd.textbbox((0, 0), ch, font=font)[2] + tracking
text_w -= tracking
asc, desc = font.getmetrics()

mark_w = int(mark_h * 0.95)
W = pad + mark_w + gap + text_w + pad

mask = Image.new("L", (W, H), 0)
md = ImageDraw.Draw(mask)

# A mark — scaled into [pad .. pad+mark_w], vertically centred
sc = mark_h / 512.0
ox = pad
oy = (H - mark_h) // 2
def P(x, y): return (ox + x * sc, oy + y * sc)
w_stroke = int(46 * sc)
thick(md, P(148, 382), P(256, 170), w_stroke)
thick(md, P(256, 170), P(364, 382), w_stroke)
thick(md, P(189, 302), P(323, 302), w_stroke)

# wordmark — vertically centred on cap height
tx = pad + mark_w + gap
ty = (H - (asc + desc)) // 2
draw_tracked_text(md, (tx, ty), text, font, tracking)

# fill the mask with a single 135deg gold sheen
yy, xx = np.mgrid[0:H, 0:W]
t = (xx + yy) / (W + H - 2)
lut = gold_lut()
idx = np.clip((t * 255).astype(int), 0, 255)
gold = np.dstack([lut[idx], np.array(mask)])      # RGBA, alpha from mask
img = Image.fromarray(gold.astype(np.uint8), "RGBA")

# apex spark — bright near-white core on top
d = ImageDraw.Draw(img)
cx, cy = P(256, 152)
d.ellipse([cx - 40 * sc, cy - 40 * sc, cx + 40 * sc, cy + 40 * sc], fill=(0xFF, 0xE8, 0x80, 60))
d.ellipse([cx - 30 * sc, cy - 30 * sc, cx + 30 * sc, cy + 30 * sc], fill=(0xFF, 0xF1, 0xB8, 255))
d.ellipse([cx - 16 * sc, cy - 18 * sc, cx + 14 * sc, cy + 12 * sc], fill=(0xFF, 0xFA, 0xDE, 255))

final = img.resize((W // SS, H // SS), Image.LANCZOS)
final.save(OUT)
print(f"wrote {OUT}  {final.size}  font={os.path.basename(font_path)}")
