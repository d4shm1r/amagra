#!/usr/bin/env python3
"""
Social-brand card generator  ->  ui/public/social-preview.png (+ docs/brand copy).

The 1280x640 card used for og:image / twitter:image. Unlike the wordmark-only
cards in gen_brand_assets.py, this one carries the full pitch: wordmark, headline,
subhead, trust line, a desktop-install line, and a version badge.

The version badge is read from infrastructure/version.py so the card never drifts
out of sync with a release again (the previous hand-made PNG got stuck at v1.5.1).

    python tools/gen_social_card.py
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Reuse the brand primitives (textile ground, wordmark fitter/masker, gold ramps).
from tools.gen_brand_assets import (  # noqa: E402
    G2, G3, G4, RICH, SHEEN,
    fit_font, textile, vgrad, wordmark_mask,
)
from infrastructure.version import __version__  # noqa: E402

# repo root: this file lives at workbench/brand/, so three levels up.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PUB = os.path.join(ROOT, "ui", "public")
BRAND = os.path.join(ROOT, "docs", "brand")
CORMORANT = "/usr/share/texlive/texmf-dist/fonts/truetype/catharsis/cormorantgaramond"
DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

W, H = 1280, 640
MX = 104                       # left margin
DARK = (46, 32, 16)            # #2E2010 ink
MUTED = (122, 104, 74)         # warm grey for the subhead
GOLD = G3                      # core gold for accented words / trust line


def cormorant(weight, size):
    return ImageFont.truetype(os.path.join(CORMORANT, f"CormorantGaramond-{weight}.ttf"), size)


def draw_tracked(draw, xy, text, font, fill, tracking):
    """Left-draw `text` with per-character `tracking` (px). Returns end-x."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking
    return x - tracking


def metallic_wordmark(base, text, target_w, top):
    """Composite the gold-metallic AMAGRA wordmark onto `base` (RGBA), left-aligned.
    Ported from gen_brand_assets.card() — shadow + vertical gold ramp + specular
    streak + top highlight. Returns the wordmark's bottom-y."""
    font, trk = fit_font(text, target_w=target_w, tracking_ratio=0.14)
    mask = wordmark_mask(text, font, trk)
    mw, mh = mask.size
    ox, oy = MX, top

    # drop shadow for separation on the light ground
    sm = Image.new("L", (W, H), 0)
    sm.paste(mask, (ox + 4, oy + 6))
    sm = sm.filter(ImageFilter.GaussianBlur(7))
    shadow = Image.new("RGBA", (W, H), (60, 42, 14, 0))
    shadow.putalpha(sm.point(lambda v: int(v * 150 / 255)))
    base.alpha_composite(shadow)

    title = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad = vgrad(mh, mw, RICH).astype(np.float32)
    yy, xx = np.mgrid[0:mh, 0:mw].astype(np.float32)
    streak = np.exp(-(((xx - yy * 0.5) - mw * 0.30) / (mw * 0.16)) ** 2)
    grad += streak[..., None] * np.array([34, 30, 12], np.float32)
    fill = Image.fromarray(np.clip(grad, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    fill.putalpha(mask)
    title.alpha_composite(fill, (ox, oy))

    # top highlight edge (engraved-metal feel)
    hl = Image.new("L", (W, H), 0); hl.paste(mask, (ox, oy - 2))
    bm = Image.new("L", (W, H), 0); bm.paste(mask, (ox, oy))
    hl_arr = np.clip(np.array(hl, int) - np.array(bm, int), 0, 255).astype(np.uint8)
    hl_img = Image.new("RGBA", (W, H), SHEEN + (0,))
    hl_img.putalpha(Image.fromarray(hl_arr).point(lambda v: int(v * 0.55)))
    title.alpha_composite(hl_img)

    base.alpha_composite(title)
    return oy + mh


def build():
    # Lower grain than the default (4.0): film noise is what bloats the PNG, and
    # a quieter ground also quantizes cleanly below (see save block).
    bg = textile(W, H, top=(245, 238, 226), bot=(228, 217, 198),
                 thread=(214, 192, 150), glow=(14, 9, 1), vignette=0.40,
                 grain=1.6, weave_amp=0.012, thread_amp=0.006).convert("RGBA")
    d = ImageDraw.Draw(bg)

    # ── wordmark ──
    wm_bottom = metallic_wordmark(bg, "AMAGRA", target_w=int(W * 0.60), top=74)

    # ── hairline + diamond flourish under the wordmark ──
    fy = wm_bottom + 34
    d.polygon([(MX, fy - 5), (MX + 5, fy), (MX, fy + 5), (MX - 5, fy)], fill=G3 + (200,))
    d.line([(MX + 16, fy), (W - MX, fy)], fill=G3 + (150,), width=2)

    # ── headline (Cormorant SemiBold) ──
    h_font = cormorant("SemiBold", 70)
    y = fy + 30
    d.text((MX, y), "See where your prompt", font=h_font, fill=DARK)
    y += 74
    d.text((MX, y), "breaks across models.", font=h_font, fill=GOLD)

    # ── subhead (Cormorant Medium) ──
    sub = cormorant("Medium", 33)
    y += 96
    d.text((MX, y), "One prompt across Claude, GPT & local models — side by side, with a divergence score.",
           font=sub, fill=MUTED)

    # ── trust + desktop lines (DejaVu Bold, uppercase, tracked gold) ──
    small = ImageFont.truetype(DEJAVU, 18)
    y += 62
    draw_tracked(d, (MX, y), "LOCAL-FIRST   ·   MIT LICENSED   ·   SELF-HOSTED",
                 small, GOLD, tracking=2)
    tiny = ImageFont.truetype(DEJAVU, 15)
    y += 34
    draw_tracked(d, (MX, y), "DESKTOP APP   ·   MAC   ·   WINDOWS   ·   LINUX",
                 tiny, (150, 120, 70), tracking=2)

    # ── version pill, bottom-right ──
    ver = f"v{__version__}"
    pill_font = ImageFont.truetype(DEJAVU, 24)
    tw = d.textlength(ver, font=pill_font)
    pw, ph = int(tw + 46), 52
    px, py = W - MX - pw, H - 96
    pill = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pill)
    grad = vgrad(ph, pw, [(0.0, G2), (0.5, G3), (1.0, G4)])
    gimg = Image.fromarray(grad, "RGB").convert("RGBA")
    rr = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(rr).rounded_rectangle([0, 0, pw - 1, ph - 1], ph // 2, fill=255)
    pill.paste(gimg, (0, 0), rr)
    ImageDraw.Draw(pill).text(((pw - tw) / 2, (ph - 30) / 2), ver, font=pill_font, fill=(28, 20, 4))
    bg.alpha_composite(pill, (px, py))

    # ── thin inset frame (premium-print feel) ──
    d.rounded_rectangle([26, 26, W - 26, H - 26], 10, outline=G3 + (70,), width=2)

    # og:image must stay small — WhatsApp won't render a preview much over ~300 KB
    # and some crawlers cap at 1 MB. An adaptive 256-colour palette + optimize cuts
    # the file ~5x while the smooth gold gradients survive (dithered).
    out = bg.convert("RGB").quantize(
        colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG
    )
    for path in (os.path.join(PUB, "social-preview.png"),
                 os.path.join(BRAND, "social-preview.png")):
        out.save(path, optimize=True)
        kb = os.path.getsize(path) // 1024
        print(f"✓ {os.path.relpath(path, ROOT)}  ({ver}, {kb} KB)")


if __name__ == "__main__":
    build()
