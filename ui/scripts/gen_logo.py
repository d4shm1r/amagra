"""Render the Amagra README wordmark — "AMAGRA" in the exact dashboard style.

Matches ui/public/landing.html .logo-text: DM Sans ExtraBold (800), letter-spacing
0.10em, and the symmetric 135deg gold gradient (g5 0% -> g2 52% -> g5 100%).
Transparent background so it reads on GitHub light and dark themes. Drawn at 3x
then downscaled with LANCZOS.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = "/home/dashmir/agentic-ai/docs/amagra-logo.png"
FONT = os.path.join(os.path.dirname(__file__), "fonts", "DMSans-ExtraBold.ttf")
SS = 3

# exact .logo-text stops: 135deg, g5/g4/g3/g2/g3/g4/g5 (symmetric metallic sheen)
STOPS = [
    (0.00, (0x6C, 0x4C, 0x00)),   # g5
    (0.18, (0x9A, 0x6C, 0x00)),   # g4
    (0.36, (0xC4, 0x88, 0x08)),   # g3
    (0.52, (0xDE, 0xB8, 0x38)),   # g2  (brightest, centre)
    (0.68, (0xC4, 0x88, 0x08)),   # g3
    (0.84, (0x9A, 0x6C, 0x00)),   # g4
    (1.00, (0x6C, 0x4C, 0x00)),   # g5
]

def gold_lut():
    out = []
    for i in range(256):
        t = i / 255.0
        for j in range(len(STOPS) - 1):
            p0, c0 = STOPS[j]; p1, c1 = STOPS[j + 1]
            if t <= p1:
                f = 0 if p1 == p0 else (t - p0) / (p1 - p0)
                out.append([int(round(c0[k] + (c1[k] - c0[k]) * f)) for k in range(3)])
                break
        else:
            out.append(list(STOPS[-1][1]))
    return np.array(out, dtype=np.uint8)

TEXT = "AMAGRA"
font_px = 200 * SS
tracking = int(0.10 * font_px)          # letter-spacing: 0.10em
pad_x = 16 * SS
pad_y = 28 * SS
font = ImageFont.truetype(FONT, font_px)

# measure with tracking
scratch = ImageDraw.Draw(Image.new("L", (4, 4)))
char_w = [scratch.textbbox((0, 0), ch, font=font)[2] for ch in TEXT]
text_w = sum(char_w) + tracking * (len(TEXT) - 1)
asc, desc = font.getmetrics()
W = text_w + 2 * pad_x
H = asc + desc + 2 * pad_y

# draw glyphs into a mask, with tracking
mask = Image.new("L", (W, H), 0)
md = ImageDraw.Draw(mask)
x = pad_x
for ch, w in zip(TEXT, char_w):
    md.text((x, pad_y), ch, font=font, fill=255)
    x += w + tracking

# fill the mask with the 135deg gradient (top-left -> bottom-right)
yy, xx = np.mgrid[0:H, 0:W]
t = (xx + yy) / (W + H - 2)
lut = gold_lut()
idx = np.clip((t * 255).astype(int), 0, 255)
rgba = np.dstack([lut[idx], np.array(mask)]).astype(np.uint8)
img = Image.fromarray(rgba, "RGBA").resize((W // SS, H // SS), Image.LANCZOS)
img.save(OUT)
print(f"wrote {OUT}  {img.size}  font=DM Sans ExtraBold")
