"""
Generate the "How it works" diagram for the README — one SVG per theme.

    python3 workbench/brand/gen_architecture_diagram.py

Writes docs/brand/how-it-works-{light,dark}.svg. The README picks between them
with a <picture> element, so the diagram follows GitHub's theme instead of
glaring white in dark mode.

SVG (not PNG) on purpose: crisp at any width, ~6 KB, and a text file — so a
change to the flow shows up as a readable diff instead of an opaque blob.

Arrowheads are drawn as explicit polygons rather than <marker> defs: GitHub
sanitizes SVG it renders in markdown, and markers are exactly the sort of thing
that gets stripped. A triangle always survives.

The gold is the brand ramp's core value from gen_brand_assets.py.
"""
from __future__ import annotations

import os
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRAND = os.path.join(ROOT, "docs", "brand")

W, H = 800, 530
CX = 400                     # the flow runs down this axis
RAIL_X = 700                 # the event rail sits just right of the widest card
FONT = ("ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,"
        "Helvetica,Arial,sans-serif")

THEMES = {
    "light": dict(ink="#1C1917", muted="#78716C", card="#FFFFFF",
                  stroke="#E7E5E4", gold="#C48808", wash="#FDF8EC", line="#D6D3D1"),
    "dark":  dict(ink="#EDEAE4", muted="#9A9590", card="#17161A",
                  stroke="#2E2C29", gold="#DEB838", wash="#241D08", line="#44403C"),
}


def card(x, y, w, h, t, fill="card", stroke="stroke", sw=1.5, rx=10):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{t[fill]}" stroke="{t[stroke]}" stroke-width="{sw}"/>')


def text(x, y, s, t, fill="ink", size=15, weight=500, anchor="middle", ls="0"):
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{t[fill]}" '
            f'font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'letter-spacing="{ls}">{escape(s)}</text>')


def head(x, y, t, facing="down", color="line", s=5):
    """An explicit arrowhead. Tip lands exactly on (x, y)."""
    pts = {
        "down":  f"{x},{y} {x - s},{y - s * 1.6} {x + s},{y - s * 1.6}",
        "up":    f"{x},{y} {x - s},{y + s * 1.6} {x + s},{y + s * 1.6}",
        "left":  f"{x},{y} {x + s * 1.6},{y - s} {x + s * 1.6},{y + s}",
        "right": f"{x},{y} {x - s * 1.6},{y - s} {x - s * 1.6},{y + s}",
    }[facing]
    return f'<polygon points="{pts}" fill="{t[color]}"/>'


def line(d, t, color="line", sw=1.5, extra=""):
    return (f'<path d="{d}" stroke="{t[color]}" stroke-width="{sw}" '
            f'fill="none" stroke-linecap="round" {extra}/>')


def down(x, y1, y2, t):
    """A straight drop with a head on the end."""
    return [line(f"M {x} {y1} V {y2 - 6}", t), head(x, y2, t, "down")]


def fork(x0, y0, xs, y1, t, r=10):
    """One trunk splitting into several drops — rounded corners, heads on ends."""
    mid = y0 + 26
    out = [line(f"M {x0} {y0} V {mid}", t)]
    for x in xs:
        sgn = 1 if x > x0 else -1
        out.append(line(
            f"M {x0} {mid} H {x - sgn * r} Q {x} {mid} {x} {mid + r} V {y1 - 6}", t))
        out.append(head(x, y1, t, "down"))
    return out


def merge(xs, y0, x1, y1, t, r=10):
    """Several drops rejoining one trunk."""
    mid = y0 + 26
    out = []
    for x in xs:
        sgn = 1 if x1 > x else -1
        out.append(line(
            f"M {x} {y0} V {mid - r} Q {x} {mid} {x + sgn * r} {mid} H {x1}", t))
    out += [line(f"M {x1} {mid} V {y1 - 6}", t), head(x1, y1, t, "down")]
    return out


def build(theme: str) -> str:
    t = THEMES[theme]
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
         f'width="{W}" height="{H}" role="img" aria-label="'
         f'How Amagra answers a question. A signal classifier takes about one '
         f'millisecond and sends most questions straight to a specialist agent; '
         f'ambiguous ones go to the LLM coordinator first. The specialist retrieves '
         f'relevant memory, generates the answer, and a critic scores it — '
         f'regenerating if the answer is weak. Every step emits an event.">']

    # ── the question ──
    o += [card(300, 24, 200, 44, t, "wash", "gold", rx=22),
          text(CX, 52, "Your question", t, size=15, weight=600)]
    o += down(CX, 68, 96, t)

    # ── signal classifier ──
    o += [card(205, 96, 390, 74, t, "card", "gold", sw=2),
          text(CX, 125, "Signal classifier", t, size=16, weight=650),
          text(CX, 148, "~1 ms  ·  domain & shape heuristics", t, "muted", 13, 400)]

    # ── the split: most go direct, the ambiguous go to the coordinator ──
    o += fork(CX, 170, [270, 530], 224, t)

    o += [card(150, 224, 240, 62, t),
          text(270, 248, "Direct route", t, size=15, weight=600),
          text(270, 269, "straight to the specialist", t, "muted", 12.5, 400)]

    o += [card(410, 224, 240, 62, t),
          text(530, 248, "Coordinator", t, size=15, weight=600),
          text(530, 269, "reasons out the ambiguous ones", t, "muted", 12.5, 400)]

    o += merge([270, 530], 286, CX, 338, t)

    # ── the specialist ──
    o += [card(165, 338, 470, 166, t, "card", "gold", sw=2),
          text(CX, 368, "Specialist agent", t, size=16, weight=650)]

    for label, y in (("Retrieves relevant memory", 402),
                     ("Generates the answer", 434),
                     ("A critic scores it", 466)):
        o += [f'<circle cx="200" cy="{y - 5}" r="3.5" fill="{t["gold"]}"/>',
              text(216, y, label, t, size=13.5, weight=450, anchor="start")]

    # the loop that makes it a loop: critic -> back to generate. It starts where
    # the critic line ends and lands where the generate line ends, so it reads as
    # a return path and not a floating bracket.
    o += [line("M 336 461 H 574 Q 590 461 590 445 Q 590 429 574 429 H 378", t,
               "gold", sw=1.5, extra='opacity="0.9"'),
          head(372, 429, t, "left", "gold", s=4.5),
          text(590, 489, "regenerate if weak", t, "gold", 11.5, 500, anchor="end")]

    # ── the event rail ──
    o += [line(f"M {RAIL_X} 40 V 504", t, "gold", sw=1.25,
               extra='stroke-dasharray="3 5" opacity="0.5"')]
    for y in (46, 133, 255, 421):          # question, classifier, route, specialist
        o += [f'<circle cx="{RAIL_X}" cy="{y}" r="3" fill="{t["gold"]}"/>']
    o += [f'<text transform="translate({RAIL_X + 24},272) rotate(-90)" '
          f'text-anchor="middle" fill="{t["muted"]}" font-family="{FONT}" '
          f'font-size="11.5" font-weight="500" letter-spacing="0.1em">'
          f'EVERY STEP EMITS AN EVENT</text>']

    return "\n".join(o + ["</svg>"]) + "\n"


def main() -> None:
    os.makedirs(BRAND, exist_ok=True)
    for theme in THEMES:
        path = os.path.join(BRAND, f"how-it-works-{theme}.svg")
        with open(path, "w") as f:
            f.write(build(theme))
        print(f"wrote {os.path.relpath(path, ROOT)}  ({os.path.getsize(path)} bytes)")


if __name__ == "__main__":
    main()
