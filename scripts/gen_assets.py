"""Generate the animated README art (assets/banner.svg, assets/demo.svg).

Pure standard library. Run:  python3 scripts/gen_assets.py
GitHub renders these SVGs (SMIL animation) when used through <img>.
"""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "assets"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', monospace"

GLYPHS = {
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
}
RAINBOW = ["#ff4d6d", "#ff9f1c", "#ffe66d", "#06d6a0", "#4cc9f0", "#a06cd5", "#ff4d6d"]
BG = "#0d1117"


def banner() -> str:
    text, px, gap = "TERM-TODO", 14, 1
    cols = len(text) * 5 + (len(text) - 1) * gap
    title_w, title_h = cols * px, 7 * px
    w, h = title_w + 140, 250
    x0, y0 = (w - title_w) // 2, 52

    # one column of pixels at a time, so a whole column shares one colour animation
    columns = {}
    col = 0
    for ch in text:
        for gx in range(5):
            columns[col] = [gy for gy in range(7) if GLYPHS[ch][gy][gx] == "1"]
            col += 1
        col += gap

    outline, fills = [], []
    for c, ys in columns.items():
        for gy in ys:
            x, y = x0 + c * px, y0 + gy * px
            outline.append(f'<rect x="{x - 3}" y="{y - 3}" width="{px + 6}" height="{px + 6}"/>')
        if ys:
            rects = "".join(
                f'<rect x="{x0 + c * px}" y="{y0 + gy * px}" width="{px}" height="{px}"/>' for gy in ys
            )
            # negative begin = phase offset, so the colours ripple across the word
            fills.append(
                f'<g fill="{RAINBOW[0]}">{rects}'
                f'<animate attributeName="fill" values="{";".join(RAINBOW)}" dur="5s" '
                f'begin="{-c * 0.09:.2f}s" repeatCount="indefinite"/></g>'
            )
    shadow = "".join(
        f'<rect x="{x0 + c * px + 5}" y="{y0 + gy * px + 7}" width="{px}" height="{px}"/>'
        for c, ys in columns.items() for gy in ys
    )

    stars = []
    for i, (sx, sy) in enumerate([(28, 28), (w - 34, 36), (36, h - 34), (w - 44, h - 30), (w // 2 + 230, 24)]):
        s = 4
        stars.append(
            f'<g fill="#e6edf3" opacity="0.2"><rect x="{sx}" y="{sy - s}" width="{s}" height="{3 * s}"/>'
            f'<rect x="{sx - s}" y="{sy}" width="{3 * s}" height="{s}"/>'
            f'<animate attributeName="opacity" values="0.15;1;0.15" dur="{2 + i * 0.7:.1f}s" '
            f'begin="{-i * 0.6:.1f}s" repeatCount="indefinite"/></g>'
        )

    tagline = "buckets  ·  notes  ·  calendar sync"
    tw = len(tagline) * 10
    ty = y0 + title_h + 56
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="term-todo">
<title>term-todo</title>
<rect width="{w}" height="{h}" rx="18" fill="{BG}"/>
<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="17" fill="none" stroke="#30363d"/>
{"".join(stars)}
<g fill="#000" opacity="0.45">{shadow}</g>
<g fill="#0d1117">{"".join(outline)}</g>
{"".join(fills)}
<text x="{w // 2 - tw // 2}" y="{ty}" font-family="{MONO}" font-size="18" fill="#8b949e" textLength="{tw}" lengthAdjust="spacingAndGlyphs">{escape(tagline)}</text>
<rect x="{w // 2 + tw // 2 + 8}" y="{ty - 16}" width="10" height="20" fill="#06d6a0">
<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1.1s" repeatCount="indefinite"/></rect>
</svg>
'''


def demo() -> str:
    cw, lh, fs = 8.4, 22, 14       # char width, line height, font size
    w, h = 760, 352
    total = 20.0                   # loop length (s)
    left, top = 26, 70
    P = "#06d6a0"                  # prompt colour

    # (kind, text, start_second)  kind: cmd = typed, out = appears at once
    script = [
        ("cmd", 'term-todo add "Ship v1" -b work -d 2026-10-20', 0.8),
        ("out", "Added #1 [work]: Ship v1 (due 2026-10-20 00:00:00)", 3.4),
        ("cmd", 'term-todo add "Book dentist" -b personal', 4.2),
        ("out", "Added #2 [personal]: Book dentist", 6.4),
        ("cmd", "term-todo list", 7.2),
        ("tbl", None, 8.4),
        ("cmd", "term-todo sync", 11.6),
        ("out", "Pushed #1 -> calendar event 7fh2k9q1…", 12.8),
        ("cmd", "term-todo ui", 14.0),
        ("out", "-> full-screen UI:  a add  e edit  space tick  s sync  q quit", 15.4),
    ]
    rows = [
        ("1", "work", "pending", "Ship v1", "2026-10-20"),
        ("2", "personal", "pending", "Book dentist", "-"),
    ]

    def reveal(start, end_vis=total - 0.6):
        """Opacity: hidden until start, visible until the loop resets."""
        a, b = start / total, end_vis / total
        return (f'<animate attributeName="opacity" calcMode="discrete" values="0;1;0" '
                f'keyTimes="0;{a:.4f};{b:.4f}" dur="{total}s" repeatCount="indefinite"/>')

    parts, clips, y = [], [], top
    for i, (kind, text, t0) in enumerate(script):
        if kind == "cmd":
            n = len(text) + 2
            width = n * cw
            t1 = t0 + max(0.8, len(text) * 0.045)
            clips.append(
                f'<clipPath id="c{i}"><rect x="{left}" y="{y - lh + 6}" height="{lh}" width="0">'
                f'<animate attributeName="width" values="0;0;{width:.1f};{width:.1f}" '
                f'keyTimes="0;{t0 / total:.4f};{t1 / total:.4f};1" dur="{total}s" repeatCount="indefinite"/>'
                f'</rect></clipPath>'
            )
            parts.append(
                f'<g clip-path="url(#c{i})"><text x="{left}" y="{y}" font-family="{MONO}" font-size="{fs}" '
                f'textLength="{width:.1f}" lengthAdjust="spacingAndGlyphs">'
                f'<tspan fill="{P}">$ </tspan><tspan fill="#e6edf3">{escape(text)}</tspan></text></g>'
            )
            y += lh
        elif kind == "out":
            parts.append(
                f'<text x="{left}" y="{y}" font-family="{MONO}" font-size="{fs}" fill="#8b949e" opacity="0" '
                f'textLength="{len(text) * cw:.1f}" lengthAdjust="spacingAndGlyphs">{escape(text)}{reveal(t0)}</text>'
            )
            y += lh
        else:  # table
            cols = [("ID", 3), ("Bucket", 10), ("Status", 9), ("Title", 14), ("Due", 12)]
            line = "".join(f"{n:<{wd + 2}}" for n, wd in cols)
            cells = []
            for r_i, r in enumerate([("ID", "Bucket", "Status", "Title", "Due")] + rows):
                txt = "".join(f"{v:<{wd + 2}}" for v, (_, wd) in zip(r, cols))
                colour = "#e6edf3" if r_i == 0 else "#c9d1d9"
                weight = "bold" if r_i == 0 else "normal"
                cells.append(
                    f'<text x="{left}" y="{y}" font-family="{MONO}" font-size="{fs}" fill="{colour}" '
                    f'font-weight="{weight}" opacity="0" xml:space="preserve" textLength="{len(line) * cw:.1f}" '
                    f'lengthAdjust="spacingAndGlyphs">{escape(txt)}{reveal(t0 + r_i * 0.35)}</text>'
                )
                y += lh
            parts.append("".join(cells))

    dots = "".join(f'<circle cx="{26 + i * 22}" cy="26" r="6.5" fill="{c}"/>'
                   for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="term-todo demo">
<title>term-todo demo</title>
<defs>{"".join(clips)}</defs>
<rect width="{w}" height="{h}" rx="12" fill="{BG}"/>
<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="none" stroke="#30363d"/>
<rect width="{w}" height="44" rx="12" fill="#161b22"/><rect y="30" width="{w}" height="14" fill="#161b22"/>
{dots}
<text x="{w // 2}" y="30" text-anchor="middle" font-family="{MONO}" font-size="12" fill="#8b949e">term-todo</text>
{"".join(parts)}
</svg>
'''


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    (OUT / "banner.svg").write_text(banner(), encoding="utf-8")
    (OUT / "demo.svg").write_text(demo(), encoding="utf-8")
    print("wrote", OUT / "banner.svg", OUT / "demo.svg")
