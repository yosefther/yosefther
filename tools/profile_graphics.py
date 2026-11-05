"""Graphics for the yosefther profile README.

Direction: a hostile 1960s supercomputer. Red phosphor on black glass, light
scanlines, a glitching name, machine readouts. Red is for display type and
accents only; running text is a warm off-white so it stays readable, and cyan
marks live signals.

Everything is drawn at the real size of GitHub's README column (846 px), so one
unit is one screen pixel. Rows of tiles are exact slices of that width with the
gap built in, so they line up with the full-width panels.

usage: uv run --with fonttools --with brotli python tools/profile_graphics.py assets
"""
import base64
import hashlib
import io
import math
import re
import sys
import urllib.parse
import urllib.request
from html import escape
from pathlib import Path

from fontTools.ttLib import TTFont

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
CACHE = Path(__file__).resolve().parent / ".font-cache"
CACHE.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

# ---------------------------------------------------------------- tokens
# Layout: 846 px column, 28 px inner padding, 16 px gaps between tiles.
COL, PAD, GAP = 846, 28, 16
FACES = {
    "D": ("Big Shoulders Display", "wght@900"),  # display, always red
    "V": ("VT323", "wght@400"),                  # terminal readouts
    "P": ("IBM Plex Mono", "wght@400"),          # running text
    "P5": ("IBM Plex Mono", "wght@500"),
    "M": ("Share Tech Mono", "wght@400"),        # small labels
}
C = dict(
    glass="#080203",
    bar="#120405",
    line="#41100C",
    dim="#E46B5D",   # labels (5.6:1 on glass)
    body="#F4E4DF",  # running text
    soft="#D2B7B1",  # secondary running text
    red="#FF2B1C",
    hot="#FFC9BD",
    cyan="#43E5EA",  # live signals only
)
ASCII = "".join(chr(c) for c in range(32, 127)) + "·→↗↓█"


def fetch(url, binary=False):
    key = CACHE / hashlib.sha1(url.encode()).hexdigest()
    if not key.exists():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        key.write_bytes(urllib.request.urlopen(req, timeout=30).read())
    data = key.read_bytes()
    return data if binary else data.decode()


def font_bytes(face, text):
    fam, axes = FACES[face]
    url = ("https://fonts.googleapis.com/css2?family=" + urllib.parse.quote(fam) + ":" + axes
           + "&text=" + urllib.parse.quote("".join(sorted(set(text)))))
    src = re.search(r"src: url\((.+?)\)", fetch(url)).group(1)
    return fetch(src, binary=True)


def face_weight(face):
    names, vals = FACES[face][1].split("@")
    return dict(zip(names.split(","), vals.split(","))).get("wght", "400")


_metrics = {}


def width(face, text, size, spacing=0.0):
    if face not in _metrics:
        f = TTFont(io.BytesIO(font_bytes(face, ASCII)))
        _metrics[face] = (f["hmtx"].metrics, f.getBestCmap(), f["head"].unitsPerEm)
    hm, cmap, upm = _metrics[face]
    total = sum(hm[cmap[ord(c)]][0] if ord(c) in cmap else upm * 0.6 for c in text)
    return total * size / upm + spacing * max(len(text) - 1, 0)


def wrap(face, text, size, max_w, spacing=0.0):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if width(face, trial, size, spacing) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + ([cur] if cur else [])


class Svg:
    """An SVG whose drawing area is a box (x0, width) inside a wider slot."""

    def __init__(self, w, h, label, x0=0.0, bw=None):
        self.w, self.h, self.label = w, h, label
        self.x0, self.bw = x0, bw or w
        self.parts, self.used, self.css, self.defs = [], {}, [], []

    def text(self, x, y, s, face, size, fill, anchor="start", spacing=0, cls="", glow=False):
        self.used.setdefault(face, set()).update(s)
        ls = f' letter-spacing="{spacing}"' if spacing else ""
        fl = ' filter="url(#glow)"' if glow and face == "D" else ""  # glow blurs small text
        self.parts.append(f'<text xml:space="preserve" x="{x:.1f}" y="{y:.1f}" class="f{face} {cls}" font-size="{size}" '
                          f'fill="{fill}" text-anchor="{anchor}"{ls}{fl}>{escape(s)}</text>')

    def add(self, s):
        self.parts.append(s)

    def render(self):
        css = []
        for face, chars in sorted(self.used.items()):
            b64 = base64.b64encode(font_bytes(face, "".join(chars))).decode()
            w = face_weight(face)
            css.append(f"@font-face{{font-family:'y{face}';font-weight:{w};src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
            css.append(f".f{face}{{font-family:'y{face}';font-weight:{w}}}")
        css += self.css + ["@media (prefers-reduced-motion:reduce){*{animation:none!important}}"]
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w:.2f} {self.h}" width="{self.w:.2f}" '
                f'height="{self.h}" role="img" aria-label="{escape(self.label)}">\n<title>{escape(self.label)}</title>\n'
                f"<style>\n" + "\n".join(css) + "\n</style>\n<defs>" + "".join(self.defs) + "</defs>\n"
                + f'<g transform="translate({self.x0:.2f},0)">\n' + "\n".join(self.parts) + "\n</g>\n</svg>\n")


BLINK = ".blink{animation:bl 1.05s steps(1) infinite}@keyframes bl{50%{opacity:0}}"
FLICKER = ".flick{animation:fl 7s steps(1) infinite}@keyframes fl{0%,100%{opacity:1}43%{opacity:.9}44%{opacity:1}}"


def crt_open(s, rx=12):
    W, H = s.bw, s.h
    s.defs.append(
        '<filter id="glow" x="-10%" y="-40%" width="120%" height="180%">'
        '<feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        '<radialGradient id="vig" cx="0.5" cy="0.45" r="0.8"><stop offset="0.6" stop-color="#000" stop-opacity="0"/>'
        '<stop offset="1" stop-color="#000" stop-opacity="0.4"/></radialGradient>'
        f'<radialGradient id="bloom" cx="0.3" cy="0.35" r="0.8"><stop offset="0" stop-color="{C["red"]}" stop-opacity="0.09"/>'
        f'<stop offset="1" stop-color="{C["red"]}" stop-opacity="0"/></radialGradient>'
        '<pattern id="scan" width="3" height="3" patternUnits="userSpaceOnUse"><rect width="3" height="1" fill="#000" fill-opacity="0.14"/></pattern>'
        f'<clipPath id="glass"><rect width="{W:.2f}" height="{H}" rx="{rx}"/></clipPath>')
    s.css += [BLINK, FLICKER]
    s.add(f'<g clip-path="url(#glass)"><rect width="{W:.2f}" height="{H}" fill="{C["glass"]}"/>'
          f'<rect width="{W:.2f}" height="{H}" fill="url(#bloom)"/><g class="flick">')


def crt_close(s, rx=12):
    W, H = s.bw, s.h
    s.add(f'</g><rect width="{W:.2f}" height="{H}" fill="url(#scan)"/><rect width="{W:.2f}" height="{H}" fill="url(#vig)"/></g>'
          f'<rect x="0.75" y="0.75" width="{W - 1.5:.2f}" height="{H - 1.5}" rx="{rx}" fill="none" stroke="{C["line"]}" stroke-width="1.5"/>')


def rule(s, y, x1=PAD, x2=None, dashed=False):
    d = ' stroke-dasharray="2 5"' if dashed else ""
    s.add(f'<line x1="{x1}" x2="{x2 if x2 is not None else s.bw - PAD:.2f}" y1="{y}" y2="{y}" stroke="{C["line"]}"{d}/>')


def label(s, x, y, text, color=None, anchor="start"):
    s.text(x, y, text, "M", 12, color or C["dim"], anchor=anchor, spacing=1.4)


def heading(s, prompt, title, y=34):
    s.text(PAD, y, "> " + prompt, "V", 18, C["dim"])
    s.text(PAD - 1, y + 38, title, "D", 36, C["red"], spacing=1, glow=True)


def para(s, x, y, text, max_w, size=13, lh=20, color=None, face="P", limit=None):
    lines = wrap(face, text, size, max_w)
    if limit:
        lines = lines[:limit]
    for i, ln in enumerate(lines):
        s.text(x, y + i * lh, ln, face, size, color or C["body"])
    return len(lines)


def slot(n, i):
    """Width of image slot i of n, and the x offset of the tile inside it."""
    sw = COL / n
    tw = (COL - (n - 1) * GAP) / n
    return sw, i * (tw + GAP) - i * sw, tw


# ---------------------------------------------------------------- header
def header():
    W, H = COL, 378
    s = Svg(W, H, "Yousef Alnawaiseh. AI engineer in Amman, Jordan. Computer vision backend at Sirocco. Open source contributor.")
    crt_open(s, rx=14)
    s.css.append(
        ".g1{animation:g1 8s steps(1) infinite}.g2{animation:g2 8s steps(1) infinite}"
        "@keyframes g1{0%,91%,100%{transform:translate(0,0);opacity:0}92%{transform:translate(-6px,0);opacity:.85}"
        "93%{transform:translate(5px,1px);opacity:.85}94%{transform:translate(-2px,0);opacity:.6}95%{opacity:0}}"
        "@keyframes g2{0%,91%,100%{transform:translate(0,0);opacity:0}92%{transform:translate(6px,0);opacity:.75}"
        "93%{transform:translate(-4px,-1px);opacity:.75}94%{transform:translate(3px,0);opacity:.5}95%{opacity:0}}"
        ".slice{animation:sl 8s steps(1) infinite}@keyframes sl{0%,91%,100%{transform:translateX(0);opacity:0}"
        "92%{transform:translateX(18px);opacity:.9}93%{transform:translateX(-12px);opacity:.9}94%{transform:translateX(5px);opacity:.9}95%{opacity:0}}")

    s.text(PAD, 34, "AMMAN, JORDAN", "V", 18, C["dim"])
    s.text(W - PAD, 34, "31.95° N   35.91° E", "V", 18, C["dim"], anchor="end")
    rule(s, 48)
    s.text(PAD, 84, "> IDENTIFY SUBJECT", "V", 21, C["red"], glow=True)

    nx, l1, l2, size = PAD - 2, 172, 258, 96

    def name(fill, cls="", glow=True, extra=""):
        s.add(f'<g class="{cls}"{extra}>')
        s.text(nx, l1, "YOUSEF", "D", size, fill, spacing=2, glow=glow)
        s.text(nx, l2, "ALNAWAISEH", "D", size, fill, spacing=2, glow=glow)
        s.add("</g>")
    name(C["cyan"], "g1", glow=False)
    name(C["red"], "g2", glow=False)
    name(C["red"])
    s.defs.append('<clipPath id="band"><rect x="0" y="214" width="560" height="16"/></clipPath>')
    name(C["hot"], "slice", glow=False, extra=' clip-path="url(#band)"')

    rx = 586
    s.add(f'<line x1="{rx - 22}" x2="{rx - 22}" y1="70" y2="268" stroke="{C["line"]}" stroke-dasharray="2 5"/>')
    rows = [("FUNCTION", "AI ENGINEER"), ("BUILDS", "CV BACKEND @ SIROCCO"), ("ALSO", "OPEN SOURCE CONTRIBUTOR")]
    for i, (k, v) in enumerate(rows):
        y = 112 + i * 58
        label(s, rx, y, k)
        s.text(rx, y + 23, v, "V", 23, C["red"], glow=True)

    rule(s, 292)
    s.text(PAD, 326, ">", "V", 21, C["red"], glow=True)
    s.text(PAD + 18, 326, "I build the vision backend for Sirocco's inspection drones, and AI tools",
           "P", 15, C["body"])
    s.text(PAD + 18, 349, "that help developers understand code.", "P", 15, C["body"])
    crt_close(s, rx=14)
    return s


# ---------------------------------------------------------------- contact keys
CONTACT = [("LINKEDIN", "in/yousef-thair-alnawaiseh"), ("EMAIL", "yousef@sirocco.digital"), ("WEB", "sirocco.digital")]


def contact_key(i):
    sw, x0, tw = slot(3, i)
    k, v = CONTACT[i]
    H = 62
    s = Svg(sw, H, f"{k.title()}: {v}", x0, tw)
    crt_open(s, rx=10)
    label(s, 18, 25, f"[{i + 1}] {k}")
    s.text(18, 47, v, "P", 14, C["body"])
    s.text(tw - 16, 26, "↗", "P", 14, C["red"], anchor="end")
    crt_close(s, rx=10)
    return s


# ---------------------------------------------------------------- now
NOW = [
    ("SIROCCO", "Computer vision backend for our autonomous inspection drones.", "CO-FOUNDER", False),
    ("CODEATLAS", "Ask questions about any code repository and get answers pointing to the exact file and line.", "IN PROGRESS", True),
    ("AGENTMEM", "A database that lets AI assistants remember facts about you across conversations and keep them up to date.", "IN PROGRESS", True),
]


def now():
    W = COL
    cw = (W - 2 * PAD) / 3
    descs = [wrap("P", d, 14, cw - 30) for _, d, _, _ in NOW]
    top = 96
    H = top + 92 + 22 * max(map(len, descs)) + 14
    s = Svg(W, H, "Now. " + " ".join(f"{n.title()}: {d} ({st.lower()})." for n, d, st, _ in NOW))
    crt_open(s)
    heading(s, "NOW", "WHAT I'M BUILDING")
    rule(s, top)
    for i, (name, _, status, live) in enumerate(NOW):
        x = PAD + i * cw
        if i:
            s.add(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{top}" y2="{H - 20}" stroke="{C["line"]}"/>')
        px = x + (0 if i == 0 else 20)
        col = C["cyan"] if live else C["dim"]
        s.add(f'<rect x="{px}" y="{top + 20}" width="7" height="11" fill="{col}"/>')
        label(s, px + 14, top + 30, status, color=col)
        s.text(px - 1, top + 62, name, "D", 26, C["red"], spacing=1, glow=True)
        for j, ln in enumerate(descs[i]):
            s.text(px, top + 90 + j * 22, ln, "P", 14, C["body"])
    crt_close(s)
    return s


# ---------------------------------------------------------------- webots
PRS = [
    ("#7048", "Merge identical vertices of WREN static meshes", "2026-10-12"),
    ("#7047", "Do not build mesh normals while loading a world", "2026-10-10"),
    ("#7043", "Fix stale camera culling after reading a WREN matrix", "2026-10-05"),
    ("#7036", "Fix duplicate light intensity scaling in PBR diffuse lighting", "2026-10-02"),
]


def webots():
    W, row, top = COL, 40, 116
    H = top + row * len(PRS) + 14
    s = Svg(W, H, "Open source. Four fixes merged into Webots, an open-source robot simulator, in WREN, its C++ "
                  "rendering engine. " + " ".join(f"{n}: {t}." for n, t, _ in PRS))
    crt_open(s)
    heading(s, "OPEN SOURCE", "FOUR FIXES IN WEBOTS")
    s.text(PAD, 98, "cyberbotics/webots · robot simulator · my changes are in WREN, its C++ renderer",
           "P", 13, C["soft"])
    lab = "4/4 MERGED"
    s.add(f'<rect x="{W - PAD - width("M", lab, 11, 1.6) - 18:.1f}" y="60" width="7" height="11" fill="{C["cyan"]}"/>')
    label(s, W - PAD, 70, lab, color=C["cyan"], anchor="end")
    for i, (num, title, date) in enumerate(PRS):
        y = top + i * row
        rule(s, y, dashed=True)
        s.text(PAD, y + 27, num, "V", 22, C["red"])
        s.text(PAD + 66, y + 26, title, "P", 14, C["body"])
        s.text(W - PAD, y + 27, date, "V", 19, C["dim"], anchor="end")
    crt_close(s)
    return s


# ---------------------------------------------------------------- card art
def art_terminal(s, x, y, w, h):
    lines = [("$ ", "spring-init new --artifact-id demo \\"), ("  ", "  --group-id com.acme \\"),
             ("  ", "  --dependencies web,data-jpa,h2"), ("> ", "GENERATING demo.zip")]
    for i, (p, ln) in enumerate(lines):
        yy = y + 26 + i * 22
        s.text(x, yy, p, "V", 19, C["red"], glow=True)
        s.text(x + width("V", "$ ", 19), yy, ln, "V", 19, C["red"] if i == 3 else C["body"], glow=i == 3)
    cx = x + width("V", "> GENERATING demo.zip", 19) + 5
    s.add(f'<rect class="blink" x="{cx:.1f}" y="{y + 26 + 66 - 14}" width="9" height="16" fill="{C["red"]}"/>')


def art_chat(s, x, y, w, h):
    rows = [("YOU", "push the fix to main", C["body"]),
            ("HERMES", "I cannot do that without approval.", C["soft"]),
            ("HERMES", "Approve: git push origin main [Y/N]", C["red"])]
    for i, (who, msg, col) in enumerate(rows):
        yy = y + 26 + i * 26
        s.text(x, yy, who, "V", 18, C["dim"])
        s.text(x + 62, yy, msg, "V", 19, col, glow=i == 2)
    cx = x + 62 + width("V", rows[2][1], 19) + 5
    s.add(f'<rect class="blink" x="{cx:.1f}" y="{y + 26 + 52 - 14}" width="9" height="16" fill="{C["red"]}"/>')


def art_raycast(s, x, y, w, h):
    """A real ray-cast frame (DDA, fish-eye corrected), like the engine renders."""
    grid = ["11111111111", "10000000001", "10111011101", "10100000101",
            "10102220101", "10000000001", "11111111111"]
    px, py, ang, fov = 1.6, 5.5, -0.12, math.radians(70)
    cols = 104
    cw = w / cols
    mid = y + h / 2
    for c in range(cols):
        ra = ang - fov / 2 + fov * (c + 0.5) / cols
        dx, dy = math.cos(ra), math.sin(ra)
        mx, my = int(px), int(py)
        ddx = abs(1 / dx) if dx else 1e9
        ddy = abs(1 / dy) if dy else 1e9
        sx, sdx = (-1, (px - mx) * ddx) if dx < 0 else (1, (mx + 1 - px) * ddx)
        sy, sdy = (-1, (py - my) * ddy) if dy < 0 else (1, (my + 1 - py) * ddy)
        while True:
            if sdx < sdy:
                sdx += ddx; mx += sx; side = 0
            else:
                sdy += ddy; my += sy; side = 1
            if grid[my][mx] != "0":
                break
        dist = ((sdx - ddx) if side == 0 else (sdy - ddy)) * math.cos(ra - ang)
        hh = min(h, h * 0.95 / max(dist, 0.05))
        hot = grid[my][mx] == "2"
        op = max(0.08, min(1, 1.3 / dist)) * (0.75 if side else 1)
        s.add(f'<rect x="{x + c * cw:.1f}" y="{mid - hh / 2:.1f}" width="{cw + 0.8:.1f}" height="{hh:.1f}" '
              f'fill="{C["hot"] if hot else C["red"]}" fill-opacity="{op * (0.9 if hot else 0.6):.2f}"/>')
    s.add(f'<path d="M{x + w / 2 - 6},{mid:.1f} h12 M{x + w / 2},{mid - 6:.1f} v12" stroke="{C["hot"]}"/>')


def art_scan(s, x, y, w, h):
    s.css.append(f".scanl{{animation:sc 4s ease-in-out infinite}}@keyframes sc{{0%,100%{{transform:translateY(0)}}"
                 f"50%{{transform:translateY({h - 18}px)}}}}")
    rows = [("SAMPLE RECORD · PAGE 1/3", C["dim"]), ("BP 128/84   HR 76   SPO2 98%", C["body"]),
            ("HBA1C 7.1%   LDL 142 MG/DL", C["body"]), ("> SEARCHING PUBMED VIA MCP", C["red"])]
    for i, (ln, col) in enumerate(rows):
        s.text(x, y + 26 + i * 22, ln, "V", 19, col, glow=i == 3)
    s.add(f'<g class="scanl"><rect x="{x - PAD + 6}" y="{y + 4}" width="{w + 2 * PAD - 12}" height="2" fill="{C["red"]}" filter="url(#glow)"/>'
          f'<rect x="{x - PAD + 6}" y="{y - 14}" width="{w + 2 * PAD - 12}" height="18" fill="{C["red"]}" fill-opacity="0.08"/></g>')


CARDS = [
    ("spring-initializr-cli", "yosefther/spring-initializr-cli", art_terminal, "SPRING BOOT FROM THE TERMINAL",
     "A CLI for start.spring.io with presets, JSON output for scripts, and a metadata cache so it still works on a flaky network.",
     "PYTHON · 14 TESTS · CI ON LINUX + WINDOWS"),
    ("hermes-telegram-assistant", "yosefther/hermes-telegram-assistant", art_chat, "AN AI THAT MUST ASK FIRST",
     "My self-hosted assistant on Telegram. Rootless Podman, one mounted folder, and my approval before anything leaves the machine.",
     "BASH · PODMAN · SYSTEMD"),
    ("raycast3d", "yosefther/rayCast3D", art_raycast, "A RAY-CASTER FROM SCRATCH",
     "DDA grid traversal, fish-eye correction and a top-down debug view of every ray. The corridor above is drawn the same way.",
     "PYTHON · PYGAME · 8 TESTS"),
    ("local-medical-assistant", "siglag/hackathon", art_scan, "A LOCAL ASSISTANT FOR DOCTORS",
     "Built at JOSA hackathon. Reads patient records with local OCR and looks up research on PubMed through an MCP agent.",
     "FASTAPI · PADDLEOCR · MCP"),
]


def card(i, slug, path, art, title, desc, facts):
    sw, x0, tw = slot(2, i % 2)
    H, bar, ah = 334, 30, 112
    s = Svg(sw, H, f"{title.capitalize()}. {desc} Repository {path}.", x0, tw)
    crt_open(s)
    s.add(f'<rect width="{tw:.2f}" height="{bar}" fill="{C["bar"]}"/>')
    s.text(16, 21, path, "V", 18, C["dim"])
    for k in range(3):
        s.add(f'<rect x="{tw - 26 - k * 16:.1f}" y="11" width="8" height="8" fill="none" stroke="{C["dim"]}"/>')
    rule(s, bar, 0, tw)
    if art is art_raycast:
        art(s, 18, bar + 12, tw - 36, ah - 18)
    else:
        art(s, 20, bar + 4, tw - 40, ah)
    rule(s, bar + ah + 10, 18, tw - 18, dashed=True)
    ty = bar + ah + 48
    s.text(18, ty, title, "D", 25, C["red"], spacing=1, glow=True)
    para(s, 20, ty + 30, desc, tw - 40, size=13.5, lh=21, limit=4)
    label(s, 20, H - 18, facts, color=C["dim"])
    crt_close(s)
    return s


# ---------------------------------------------------------------- more repos
MORE = [
    ("TODO_GOLANG", "Go + SQLite REST API with a React and TypeScript frontend.", "GO · REACT"),
    ("NETWORK", "UDP sockets and a raw packet sniffer, in C and Python.", "C · PYTHON"),
    ("ALIEN-INVASION", "An arcade shooter in Pygame, with headless tests.", "PYTHON · PYGAME"),
]


def more_tile(i):
    sw, x0, tw = slot(3, i)
    name, desc, tech = MORE[i]
    H = 136
    s = Svg(sw, H, f"{name.title()}: {desc}", x0, tw)
    crt_open(s, rx=10)
    label(s, 18, 26, "MORE ON GITHUB")
    s.text(tw - 18, 27, "↗", "P", 15, C["red"], anchor="end", glow=True)
    s.text(17, 56, name, "D", 21, C["red"], spacing=1, glow=True)
    para(s, 18, 80, desc, tw - 36, size=13, lh=20, limit=3)
    crt_close(s, rx=10)
    return s


# ---------------------------------------------------------------- stack
STACK = [
    ("LANGUAGES", "Python · Go · TypeScript · C++ · C# · C"),
    ("AI + VISION", "OpenCV · PaddleOCR · Ollama · MCP agents"),
    ("BACKEND", "FastAPI · Go net/http · SQLite · React"),
    ("SYSTEMS", "Linux · Podman · systemd · GitHub Actions"),
    ("ASK ME ABOUT", "drones · computer vision · ray casting · sandboxing AI agents"),
]


def stack():
    W, row, top = COL, 38, 96
    H = top + row * len(STACK) + 14
    s = Svg(W, H, "Stack. " + " ".join(f"{k.title()}: {v}." for k, v in STACK))
    crt_open(s)
    heading(s, "STACK", "TOOLS LOADED")
    for i, (k, v) in enumerate(STACK):
        y = top + i * row
        rule(s, y, dashed=True)
        label(s, PAD, y + 23, k, color=C["cyan"] if k == "ASK ME ABOUT" else None)
        s.text(PAD + 150, y + 24, v, "P", 14.5, C["body"])
    crt_close(s)
    return s


# ---------------------------------------------------------------- write
# Files get a content hash in their name: GitHub's image proxy caches by URL, so a
# changed image needs a new name or visitors keep seeing the old one.
names = {}


def save(name, svg):
    data = svg.render()
    tag = hashlib.sha1(data.encode()).hexdigest()[:8]
    fname = f"{name}-{tag}.svg"
    (OUT / fname).write_text(data)
    names[name] = f"{OUT.name}/{fname}"


for old in OUT.glob("*.svg"):
    old.unlink()
save("header", header())
for i, (k, _) in enumerate(CONTACT):
    save(f"key-{k.lower()}", contact_key(i))
save("now", now())
save("webots", webots())
for i, c in enumerate(CARDS):
    save(f"card-{c[0]}", card(i, *c))
for i, m in enumerate(MORE):
    save(f"more-{m[0].lower()}", more_tile(i))
save("stack", stack())


def a(href, name, alt, w):
    return f'<a href="{href}"><img src="{names[name]}" alt="{escape(alt)}" width="{w}"></a>'


def img(name, alt):
    return f'<img src="{names[name]}" alt="{escape(alt)}" width="100%">'


LINKS = {
    "linkedin": "https://www.linkedin.com/in/yousef-thair-alnawaiseh",
    "email": "mailto:yousef@sirocco.digital",
    "web": "https://www.sirocco.digital/",
    "spring-initializr-cli": "https://github.com/yosefther/spring-initializr-cli",
    "hermes-telegram-assistant": "https://github.com/yosefther/hermes-telegram-assistant",
    "raycast3d": "https://github.com/yosefther/rayCast3D",
    "local-medical-assistant": "https://github.com/siglag/hackathon",
    "todo_golang": "https://github.com/yosefther/TODO_golang",
    "network": "https://github.com/yosefther/Network",
    "alien-invasion": "https://github.com/yosefther/Alien-Invasion",
}
keys = "".join(a(LINKS[k.lower()], f"key-{k.lower()}", f"{k.title()}: {v}", "33.33%") for k, v in CONTACT)
cards = [a(LINKS[c[0]], f"card-{c[0]}", f"{c[1]}: {c[3].capitalize()}", "50%") for c in CARDS]
more = "".join(a(LINKS[m[0].lower()], f"more-{m[0].lower()}", f"{m[0]}: {m[1]}", "33.33%") for m in MORE)
readme = "\n".join([
    "<!-- Generated by tools/profile_graphics.py. Edit the script, not this file. -->",
    "<p>" + img("header", "Yousef Alnawaiseh. AI engineer in Amman, Jordan. Computer vision backend at Sirocco. Open source contributor.") + "</p>",
    "<p>" + keys + "</p>",
    "<p>" + img("now", "Now: Sirocco (co-founder), CodeAtlas and agentmem (both in progress)") + "</p>",
    "<p>" + a("https://github.com/cyberbotics/webots/pulls?q=is%3Apr+author%3Ayosefther+is%3Amerged", "webots",
              "Open source: four fixes merged into the Webots renderer", "100%") + "</p>",
    "<p>" + "".join(cards[:2]) + "</p>",
    "<p>" + "".join(cards[2:]) + "</p>",
    "<p>" + more + "</p>",
    "<p>" + img("stack", "Stack and things to ask me about") + "</p>",
    '<p><img src="https://raw.githubusercontent.com/yosefther/yosefther/output/github-snake-dark.svg" '
    'alt="Snake eating my contribution graph" width="100%"></p>',
]) + "\n"
(OUT.parent / "README.md").write_text(readme)
print("ok:", len(names), "images + README.md")
