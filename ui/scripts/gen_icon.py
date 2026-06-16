"""Render the Amagra gold mark (matching ui/public/icon.svg) to PNG/ICO.

Drawn at 4x supersample then downscaled with LANCZOS for crisp small sizes.
"""
import numpy as np
from PIL import Image, ImageDraw

OUT = "/home/dashmir/agentic-ai/ui/public"
S = 512
SS = 4               # supersample factor
N = S * SS

# 5-step gold ramp (g1..g5) — positions match the SVG linearGradient
STOPS = [
    (0.00, (0xFF, 0xE8, 0x80)),
    (0.28, (0xDE, 0xB8, 0x38)),
    (0.55, (0xC4, 0x88, 0x08)),
    (0.80, (0x9A, 0x6C, 0x00)),
    (1.00, (0x6C, 0x4C, 0x00)),
]

def ramp(t):
    """Interpolate the gold ramp at t in [0,1]."""
    for i in range(len(STOPS) - 1):
        p0, c0 = STOPS[i]
        p1, c1 = STOPS[i + 1]
        if t <= p1:
            f = 0 if p1 == p0 else (t - p0) / (p1 - p0)
            return tuple(int(round(c0[k] + (c1[k] - c0[k]) * f)) for k in range(3))
    return STOPS[-1][1]

def gold_layer(n):
    """Diagonal (135deg) gold gradient as an RGB array, n x n."""
    yy, xx = np.mgrid[0:n, 0:n]
    t = (xx + yy) / (2 * (n - 1))
    # precompute a 256-entry LUT for speed
    lut = np.array([ramp(i / 255.0) for i in range(256)], dtype=np.uint8)
    idx = np.clip((t * 255).astype(int), 0, 255)
    return lut[idx]  # n,n,3

def rounded_mask(n, rx):
    m = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, n - 1, n - 1], radius=rx, fill=255)
    return m

def tile_bg(n):
    """Vertical umber gradient #2A1D0C -> #160F05."""
    top = np.array([0x2A, 0x1D, 0x0C], dtype=float)
    bot = np.array([0x16, 0x0F, 0x05], dtype=float)
    f = (np.arange(n) / (n - 1))[:, None]
    col = (top[None, :] * (1 - f) + bot[None, :] * f)  # n,3
    arr = np.repeat(col[:, None, :], n, axis=1).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")

def thick_segment(draw, p0, p1, w, fill):
    draw.line([p0, p1], fill=fill, width=w)
    r = w // 2
    for (x, y) in (p0, p1):
        draw.ellipse([x - r, y - r, x + r, y + r], fill=fill)

def build(n):
    sc = n / S
    def P(x, y): return (x * sc, y * sc)

    # tile background, clipped to rounded rect
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    bg = tile_bg(n)
    img.paste(bg, (0, 0), rounded_mask(n, int(116 * sc)))

    # thin gold ring
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([7 * sc, 7 * sc, n - 1 - 7 * sc, n - 1 - 7 * sc],
                        radius=int(110 * sc), outline=(0xC4, 0x88, 0x08, 61),
                        width=max(1, int(3 * sc)))

    # the A, drawn into a mask then filled with the gold gradient
    mask = Image.new("L", (n, n), 0)
    md = ImageDraw.Draw(mask)
    w = int(46 * sc)
    thick_segment(md, P(148, 382), P(256, 170), w, 255)
    thick_segment(md, P(256, 170), P(364, 382), w, 255)
    thick_segment(md, P(189, 302), P(323, 302), w, 255)
    gold = Image.fromarray(gold_layer(n), "RGB").convert("RGBA")
    img.paste(gold, (0, 0), mask)

    # apex spark: soft glow + bright core
    d = ImageDraw.Draw(img)
    cx, cy = P(256, 152)
    rg = 52 * sc
    d.ellipse([cx - rg, cy - rg, cx + rg, cy + rg], fill=(0xFF, 0xE8, 0x80, 46))
    rc = 34 * sc
    # radial-ish core: light center over gold edge
    d.ellipse([cx - rc, cy - rc, cx + rc, cy + rc], fill=(0xFF, 0xE8, 0x80, 255))
    rl = 20 * sc
    d.ellipse([cx - rl - 6 * sc, cy - rl - 8 * sc, cx - rl + 2 * rl, cy - rl + 2 * rl],
              fill=(0xFF, 0xF6, 0xCE, 235))
    return img

master = build(N).resize((S, S), Image.LANCZOS)

# PNG exports
master.save(f"{OUT}/logo512.png")
master.resize((192, 192), Image.LANCZOS).save(f"{OUT}/logo192.png")
master.resize((180, 180), Image.LANCZOS).save(f"{OUT}/apple-touch-icon.png")

# favicon.ico (multi-res)
ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
master.save(f"{OUT}/favicon.ico", sizes=ico_sizes)
# also a 32px png favicon for modern <link>
master.resize((32, 32), Image.LANCZOS).save(f"{OUT}/favicon-32.png")

print("wrote: icon.svg (manual), logo512/192.png, apple-touch-icon.png, favicon.ico, favicon-32.png")
