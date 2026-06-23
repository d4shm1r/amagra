#!/usr/bin/env python3
"""
Amagra brand-asset generator.

Produces:
  1. Transparent gold-gradient "A" favicon set  -> ui/public/
       icon.svg, favicon.ico, favicon-32.png, logo192.png, logo512.png
       apple-touch-icon.png  (opaque tile — iOS flattens transparency)
  2. Three gold-wordmark marketing cards (1200x630) -> docs/brand/
       amagra-title-light.png      (warm-white)
       amagra-title-black-gold.png (black + gold)
       amagra-title-navy.png       (dark navy)

Gold ramp + Cormorant Garamond match the in-app wordmark (theme.js).
Backgrounds are a procedural premium textile (subtle woven twill + grain +
vignette + center glow) — never solid, but quiet so the title leads.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB  = os.path.join(ROOT, "ui", "public")
BRAND = os.path.join(ROOT, "docs", "brand")
FONT_PATH = "/usr/share/texlive/texmf-dist/fonts/truetype/catharsis/cormorantgaramond/CormorantGaramond-SemiBold.ttf"

# ── Brand gold ramp (theme.js GOLD g1..g5) ──────────────────────────────
G1 = (255, 232, 128)   # #FFE880  bright
G2 = (222, 184, 56)    # #DEB838
G3 = (196, 136, 8)     # #C48808  core
G4 = (154, 108, 0)     # #9A6C00  deep
G5 = (108, 76, 0)      # #6C4C00  shadow
SHEEN = (255, 247, 214)  # near-white specular


# ── gradient helpers ────────────────────────────────────────────────────
def _ramp(stops, t):
    """stops = [(pos, (r,g,b)), ...] sorted by pos; t in [0,1]."""
    t = max(0.0, min(1.0, t))
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        if p0 <= t <= p1:
            f = 0 if p1 == p0 else (t - p0) / (p1 - p0)
            return tuple(int(round(c0[k] + (c1[k] - c0[k]) * f)) for k in range(3))
    return stops[-1][1]


# Metallic vertical ramp for the wordmark — bright sheen band mid-height.
METAL = [
    (0.00, G4), (0.09, G3), (0.22, G2), (0.34, G1),
    (0.45, SHEEN), (0.55, G1), (0.66, G2), (0.80, G3),
    (0.92, G4), (1.00, G5),
]
# Richer, deeper ramp for wordmarks on LIGHT grounds (more gold, less sheen).
RICH = [
    (0.00, G5), (0.12, G4), (0.30, G3), (0.45, G2), (0.52, G1),
    (0.60, G2), (0.78, G3), (0.90, G4), (1.00, G5),
]
# Diagonal ramp for the icon "A".
DIAG = [(0.0, G1), (0.28, G2), (0.55, G3), (0.80, G4), (1.0, G5)]


def vgrad(h, w, stops):
    col = np.array([_ramp(stops, y / max(1, h - 1)) for y in range(h)], dtype=np.uint8)
    return np.repeat(col[:, None, :], w, axis=1)


def diag_fill(w, h, stops):
    yy, xx = np.mgrid[0:h, 0:w]
    t = (xx + yy) / max(1, (w + h - 2))
    lut = np.array([_ramp(stops, i / 255) for i in range(256)], dtype=np.uint8)
    idx = (t * 255).astype(np.uint8)
    return lut[idx]


# ════════════════════════════════════════════════════════════════════════
#  ICON  —  the gold "A" mark (geometry mirrors public/icon.svg)
# ════════════════════════════════════════════════════════════════════════
def a_mark(N=512):
    """Return RGBA image of the gold A + apex spark on transparent ground."""
    s = N / 512.0
    P = lambda x, y: (x * s, y * s)
    p1, ap, p3 = P(148, 382), P(256, 170), P(364, 382)
    b1, b2 = P(189, 302), P(323, 302)
    spark = P(256, 152)
    sw = int(round(46 * s))
    r = sw / 2

    mask = Image.new("L", (N, N), 0)
    d = ImageDraw.Draw(mask)
    for a, b in [(p1, ap), (ap, p3), (b1, b2)]:
        d.line([a, b], fill=255, width=sw)
    for (x, y) in [p1, ap, p3, b1, b2]:               # round the caps/joins
        d.ellipse([x - r, y - r, x + r, y + r], fill=255)

    gold = Image.fromarray(diag_fill(N, N, DIAG), "RGB").convert("RGBA")
    gold.putalpha(mask)

    out = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    out.alpha_composite(gold)

    # apex spark: soft glow + bright radial core
    gx, gy = spark
    glow = Image.new("L", (N, N), 0)
    ImageDraw.Draw(glow).ellipse([gx - 56 * s, gy - 56 * s, gx + 56 * s, gy + 56 * s], fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(14 * s))
    glow_img = Image.new("RGBA", (N, N), G1 + (0,)); glow_img.putalpha(glow)
    out.alpha_composite(glow_img)

    cr = 34 * s
    core = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    cd = ImageDraw.Draw(core)
    steps = 28
    for i in range(steps, 0, -1):
        f = i / steps
        col = _ramp([(0.0, SHEEN), (0.5, G1), (1.0, G2)], 1 - f)
        rr = cr * f
        cd.ellipse([gx - rr, gy - rr, gx + rr, gy + rr], fill=col + (255,))
    out.alpha_composite(core)
    return out


def warm_tile(N=512):
    """Opaque rounded warm-umber tile w/ gold ring (for apple-touch)."""
    grad = np.zeros((N, N, 3), np.uint8)
    top, bot = (42, 29, 12), (22, 15, 5)
    for y in range(N):
        f = y / (N - 1)
        grad[y, :] = [int(top[k] + (bot[k] - top[k]) * f) for k in range(3)]
    img = Image.fromarray(grad, "RGB").convert("RGBA")
    rad = int(N * 0.227)
    msk = Image.new("L", (N, N), 0)
    ImageDraw.Draw(msk).rounded_rectangle([0, 0, N - 1, N - 1], rad, fill=255)
    tile = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    tile.paste(img, (0, 0), msk)
    ring = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    ImageDraw.Draw(ring).rounded_rectangle(
        [int(N * .014)] * 2 + [N - 1 - int(N * .014)] * 2,
        rad - int(N * .012), outline=G3 + (90,), width=max(2, int(N * .006)))
    tile.alpha_composite(ring)
    return tile


def build_favicons():
    mark = a_mark(512)
    # transparent rasters
    mark.save(os.path.join(PUB, "logo512.png"))
    mark.resize((192, 192), Image.LANCZOS).save(os.path.join(PUB, "logo192.png"))
    mark.resize((32, 32), Image.LANCZOS).save(os.path.join(PUB, "favicon-32.png"))
    ico_sizes = [16, 32, 48, 64]
    mark.save(os.path.join(PUB, "favicon.ico"),
              sizes=[(s, s) for s in ico_sizes])
    # apple-touch: A on opaque tile
    tile = warm_tile(512)
    inset = mark.resize((int(512 * .82),) * 2, Image.LANCZOS)
    off = (512 - inset.width) // 2
    tile.alpha_composite(inset, (off, off))
    tile.convert("RGB").save(os.path.join(PUB, "apple-touch-icon.png"))
    # transparent SVG (no tile/ring)
    with open(os.path.join(PUB, "icon.svg"), "w") as f:
        f.write(ICON_SVG)
    print("✓ favicons (transparent gold A) + apple-touch tile")


ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512" role="img" aria-label="Amagra">
  <title>Amagra</title>
  <defs>
    <linearGradient id="amagra-gold" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"   stop-color="#FFE880"/>
      <stop offset="28%"  stop-color="#DEB838"/>
      <stop offset="55%"  stop-color="#C48808"/>
      <stop offset="80%"  stop-color="#9A6C00"/>
      <stop offset="100%" stop-color="#6C4C00"/>
    </linearGradient>
    <radialGradient id="amagra-spark" cx="42%" cy="36%" r="62%">
      <stop offset="0%"   stop-color="#FFF6CE"/>
      <stop offset="50%"  stop-color="#FFE880"/>
      <stop offset="100%" stop-color="#DEB838"/>
    </radialGradient>
  </defs>
  <!-- transparent background: gold A mark only -->
  <g fill="none" stroke="url(#amagra-gold)" stroke-width="46"
     stroke-linecap="round" stroke-linejoin="round">
    <path d="M148 382 L256 170"/>
    <path d="M256 170 L364 382"/>
    <path d="M189 302 L323 302"/>
  </g>
  <circle cx="256" cy="152" r="52" fill="#FFE880" opacity="0.18"/>
  <circle cx="256" cy="152" r="34" fill="url(#amagra-spark)"/>
</svg>
'''


# ════════════════════════════════════════════════════════════════════════
#  MARKETING CARDS  —  gold wordmark on premium textile
# ════════════════════════════════════════════════════════════════════════
def textile(w, h, top, bot, thread, glow, vignette=0.45, grain=4.0,
            weave_amp=0.020, thread_amp=0.010):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    fy = yy / (h - 1)
    base = np.empty((h, w, 3), np.float32)
    for k in range(3):
        base[..., k] = top[k] + (bot[k] - top[k]) * fy

    # woven twill: two diagonal carriers + finer warp/weft threads
    twill = (np.sin((xx + yy) / 5.0) + np.sin((xx - yy) / 5.0)) * 0.5
    threads = (np.sin(xx / 3.0) + np.sin(yy / 3.0)) * 0.5
    tcol = np.array(thread, np.float32) - (top[0] + bot[0]) / 2.0
    mod = 1.0 + twill * weave_amp + threads * thread_amp
    base *= mod[..., None]
    base += (twill * 0.5 + threads * 0.5)[..., None] * tcol * 0.06

    # organic grain
    rng = np.random.default_rng(7)
    noise = rng.normal(0, grain, (h, w, 1)).astype(np.float32)
    base += noise

    # center gold glow (screen-ish add)
    cx, cy = w / 2, h * 0.46
    rr = np.sqrt(((xx - cx) / (w * 0.55)) ** 2 + ((yy - cy) / (h * 0.55)) ** 2)
    g = np.clip(1 - rr, 0, 1) ** 2.0
    base += g[..., None] * np.array(glow, np.float32)

    # vignette
    rv = np.sqrt(((xx - w / 2) / (w * 0.62)) ** 2 + ((yy - h / 2) / (h * 0.62)) ** 2)
    vig = 1 - np.clip(rv - 0.55, 0, 1) * vignette
    base *= vig[..., None]

    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB")


def fit_font(text, target_w, tracking_ratio):
    size = 200
    f = ImageFont.truetype(FONT_PATH, size)
    adv = sum(f.getlength(c) for c in text) + tracking_ratio * size * (len(text) - 1)
    size = int(size * target_w / adv)
    return ImageFont.truetype(FONT_PATH, size), tracking_ratio * size


def wordmark_mask(text, font, tracking, pad=40):
    asc, desc = font.getmetrics()
    advs = [font.getlength(c) for c in text]
    total = int(sum(advs) + tracking * (len(text) - 1)) + pad * 2
    H = asc + desc + pad * 2
    m = Image.new("L", (total, H), 0)
    d = ImageDraw.Draw(m)
    x = pad
    for c, a in zip(text, advs):
        d.text((x, pad), c, font=font, fill=255)
        x += a + tracking
    bbox = m.getbbox()
    return m.crop(bbox)


def card(path, top, bot, thread, glow, vignette, frame_alpha, shadow_rgba,
         metal=METAL, outline_alpha=0, weave_amp=0.020, thread_amp=0.010,
         W=1200, H=630):
    bg = textile(W, H, top, bot, thread, glow, vignette=vignette,
                 weave_amp=weave_amp, thread_amp=thread_amp)

    font, trk = fit_font("AMAGRA", target_w=int(W * 0.66), tracking_ratio=0.14)
    mask = wordmark_mask("AMAGRA", font, trk)
    mw, mh = mask.size
    ox, oy = (W - mw) // 2, int(H * 0.5 - mh / 2)

    # drop shadow for separation
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sm = Image.new("L", (W, H), 0)
    sm.paste(mask, (ox + 4, oy + 7))
    sm = sm.filter(ImageFilter.GaussianBlur(7))
    shadow = Image.new("RGBA", (W, H), shadow_rgba[:3] + (0,))
    shadow.putalpha(sm.point(lambda v: int(v * shadow_rgba[3] / 255)))
    bg = Image.alpha_composite(bg.convert("RGBA"), shadow)

    title = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # thin deep-gold edge for crisp separation on light grounds
    if outline_alpha:
        base_full = Image.new("L", (W, H), 0); base_full.paste(mask, (ox, oy))
        edge = np.clip(np.array(base_full.filter(ImageFilter.MaxFilter(5)), int)
                       - np.array(base_full, int), 0, 255).astype(np.uint8)
        edge_img = Image.new("RGBA", (W, H), G5 + (0,))
        edge_img.putalpha(Image.fromarray(edge).point(lambda v: int(v * outline_alpha / 255)))
        title.alpha_composite(edge_img)

    # metallic gold fill + diagonal specular streak
    grad = vgrad(mh, mw, metal).astype(np.float32)
    yy, xx = np.mgrid[0:mh, 0:mw].astype(np.float32)
    streak = np.exp(-(((xx - yy * 0.5) - mw * 0.30) / (mw * 0.16)) ** 2)
    grad += streak[..., None] * np.array([34, 30, 12], np.float32)
    grad = np.clip(grad, 0, 255).astype(np.uint8)
    fill = Image.fromarray(grad, "RGB").convert("RGBA")
    fill.putalpha(mask)
    title.alpha_composite(fill, (ox, oy))

    # top highlight edge (engraved-metal feel)
    hl = Image.new("L", (W, H), 0)
    hl.paste(mask, (ox, oy - 2))
    hl_only = Image.new("L", (W, H), 0)
    base_m = Image.new("L", (W, H), 0); base_m.paste(mask, (ox, oy))
    hl_arr = np.clip(np.array(hl, int) - np.array(base_m, int), 0, 255).astype(np.uint8)
    hl_img = Image.new("RGBA", (W, H), SHEEN + (0,))
    hl_img.putalpha(Image.fromarray(hl_arr).point(lambda v: int(v * 0.55)))
    title.alpha_composite(hl_img)

    out = Image.alpha_composite(bg, title)

    # subtle flourish: centered hairline + two diamonds, under the title
    d = ImageDraw.Draw(out)
    fy = oy + mh + int(H * 0.085)
    half = int(W * 0.16)
    cx = W // 2
    d.line([(cx - half, fy), (cx - 26, fy)], fill=G3 + (frame_alpha,), width=2)
    d.line([(cx + 26, fy), (cx + half, fy)], fill=G3 + (frame_alpha,), width=2)
    for dx in (-half, 0, half):
        d.polygon([(cx + dx, fy - 5), (cx + dx + 5, fy),
                   (cx + dx, fy + 5), (cx + dx - 5, fy)], fill=G2 + (frame_alpha + 40,))

    # thin inset frame for a "premium print" feel
    inset = 26
    d.rounded_rectangle([inset, inset, W - inset, H - inset], 10,
                        outline=G3 + (frame_alpha,), width=2)

    out.convert("RGB").save(path)
    print(f"✓ {os.path.relpath(path, ROOT)}")


def build_cards():
    # 1 — warm white (current theme)
    card(os.path.join(BRAND, "amagra-title-light.png"),
         top=(245, 238, 226), bot=(228, 217, 198), thread=(214, 192, 150),
         glow=(14, 9, 1), vignette=0.40, frame_alpha=70,
         shadow_rgba=(60, 42, 14, 150), metal=RICH, outline_alpha=150,
         weave_amp=0.012, thread_amp=0.006)
    # 2 — black + gold
    card(os.path.join(BRAND, "amagra-title-black-gold.png"),
         top=(26, 19, 9), bot=(12, 9, 4), thread=(74, 58, 20),
         glow=(40, 28, 6), vignette=0.55, frame_alpha=95,
         shadow_rgba=(0, 0, 0, 150))
    # 3 — dark navy
    card(os.path.join(BRAND, "amagra-title-navy.png"),
         top=(15, 26, 56), bot=(8, 15, 36), thread=(40, 60, 108),
         glow=(30, 30, 10), vignette=0.50, frame_alpha=90,
         shadow_rgba=(2, 6, 20, 150))


if __name__ == "__main__":
    os.makedirs(BRAND, exist_ok=True)
    build_favicons()
    build_cards()
    print("done.")
