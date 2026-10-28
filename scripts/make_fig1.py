#!/usr/bin/env python3
# Fig 1 (architecture) — final vector render, designed at true print size.
# Canvas: 3.5 in (IEEE single column) x 2.0 in; 1 data unit = 1 pt, so font sizes
# are final sizes (titles 6.5pt, body 5.4-6.2pt). Replaces the interim render
# (make_fig1_interim.bak.py) whose 7.16in-wide canvas shrank text to ~3pt at column width.
# Design source: HANDOFF.md §一 content list + paper/figs/fig1_arch.excalidraw.
# Visual argument (item 8): two tenants converge into a narrowing three-stage
# funnel; one stage drops downward; the end node loops back to the tenants.
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans"],   # matches figs 2-5 (server renders had no Arial)
    "pdf.fonttype": 42, "svg.fonttype": "path",   # path: SVG must not depend on viewer fonts
})

W, H = 252.0, 150.0                       # pt == 3.5 in x 2.0 in
NEUT, SIG, ACC, OK = "#8C8C8C", "#1F5FA9", "#C0504D", "#2E7D5B"
DARK = "#3A3A3A"
F_RED, F_BLUE, F_GRAY, F_GREEN = "#F6E4E4", "#E8F0F8", "#F2F2F2", "#EAF3EE"

fig = plt.figure(figsize=(W / 72, H / 72))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")

FITCHECK = []   # (text artist, max width in pt, label, owner box name or None)
BOXES = []      # (name, x, y, w, h)
SEGS = []       # (name, x1, y1, x2, y2)

def box(x, y, w, h, fc, ec, lw=1.0, rounding=2.0, name=""):
    BOXES.append((name or f"box@{x:.0f},{y:.0f}", x, y, w, h))
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                 boxstyle=f"round,pad=0,rounding_size={rounding}",
                 fc=fc, ec=ec, lw=lw, mutation_scale=1))

def txt(x, y, s, fs, color, weight="normal", style="normal", max_w=None, name="", owner=None):
    t = ax.text(x, y, s, fontsize=fs, color=color, fontweight=weight,
                style=style, ha="center", va="center", linespacing=1.12)
    if max_w:
        FITCHECK.append((t, max_w, name or s.split("\n")[0][:24], owner))
    return t

def boxtext(x, y, w, h, title, body, tcolor, bcolor, tfs=6.5, bfs=6.2):
    cx = x + w / 2
    n_body = len(body.split("\n")) if body else 0
    total = tfs * 1.15 + n_body * bfs * 1.16 if body else tfs * 1.15
    top = y + h - (h - total) / 2
    txt(cx, top - tfs * 0.55, title, tfs, tcolor, weight="bold",
        max_w=w - 6, name=title, owner=title)
    if body:
        by = top - tfs * 1.15 - bfs * 0.58 - (n_body - 1) * bfs * 0.58
        txt(cx, by, body, bfs, bcolor, max_w=w - 6,
            name=body.split("\n")[0][:24], owner=title)

def arrow(p1, p2, color, lw=1.2, style="-|>", ms=7, name=""):
    SEGS.append((name or f"arrow{p1}->{p2}", p1[0], p1[1], p2[0], p2[1]))
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=ms,
                 color=color, lw=lw, shrinkA=0, shrinkB=0))

def line(*pts, color, lw=1.0, name=""):
    for a, b in zip(pts, pts[1:]):
        SEGS.append((name or f"line{a}->{b}", a[0], a[1], b[0], b[1]))
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=color, lw=lw, solid_joinstyle="round",
            solid_capstyle="round", zorder=1)

# --- tenants (top) -----------------------------------------------------------
box(8, 122, 88, 26, F_RED, ACC, name="malicious xApp")
boxtext(8, 122, 88, 26, "malicious xApp", "wire-rate / churn / async", ACC, ACC, bfs=5.5)
box(104, 122, 86, 26, F_BLUE, SIG, name="benign xApp")
boxtext(104, 122, 86, 26, "benign xApp", "(monitoring)\nown (σ,ρ) bucket", SIG, SIG, bfs=5.5)

arrow((56, 122), (82, 114.5), ACC, lw=1.3)
txt(32, 118, "E42AP / SCTP", 5.4, NEUT, max_w=44, name="E42AP mal")
arrow((147, 122), (162, 114.5), SIG, lw=1.3)
txt(120, 118, "E42AP / SCTP", 5.4, NEUT, max_w=44, name="E42AP ben")

# --- three-stage narrowing funnel (L0 -> L1 -> L2) ---------------------------
box(33, 90, 170, 24, F_GRAY, NEUT, name="L0 transport")
boxtext(33, 90, 170, 24, "L0 transport",
        "nftables SCTP-chunk filter + eBPF\nassociation token buckets", DARK, DARK)
arrow((104, 90), (104, 84.5), NEUT)

box(64, 50, 108, 32, F_BLUE, SIG, lw=1.5, name="L1 pre-decode")          # L1 = visual emphasis
boxtext(64, 50, 108, 32, "L1 pre-decode",
        "O(1) two-byte classify\ngreedy (σ,ρ) shaper\nwhitelist pc ∈ {0x0f,0x10}", SIG, DARK)
arrow((104, 50), (104, 38.5), NEUT)

box(79, 14, 78, 24, F_GRAY, NEUT, name="L2 application")
boxtext(79, 14, 78, 24, "L2 application", "scope CAP\nrate RATE/s", DARK, DARK)

# --- silent drop at L1 (red, downward) ---------------------------------------
arrow((64, 62), (48, 62), ACC, lw=1.3)
txt(33, 50, "silent drop, no\nreflected error\n(RFC 6633)", 5.4, ACC, max_w=54, name="drop")

# --- admitted stream -> E2 peer ----------------------------------------------
arrow((157, 26), (178, 50), SIG, lw=2.0, ms=8, name="admitted-arrow")
txt(140, 44, "admitted ≤ σ+ρt", 6.0, SIG, weight="bold", max_w=62, name="admitted")

# --- E2 node = protocol peer (green) -----------------------------------------
box(178, 20, 72, 48, F_GREEN, OK, name="E2 node\nprotocol peer")
boxtext(178, 20, 72, 48, "E2 node\nprotocol peer",
        "peer admission state\nlease clock · E2-side\nSubscriptionDelete", OK, DARK,
        tfs=6.2, bfs=5.6)
arrow((216, 68), (216, 74), OK, lw=1.1)
box(180, 74, 70, 18, "#FFFFFF", OK, name="bounded")
txt(215, 83, "bounded standing state\n+ indications to RIC", 5.4, OK, max_w=66,
    name="bounded", owner="bounded")

# --- lease loop back to tenants (green) --------------------------------------
line((216, 20), (216, 5), (3, 5), (3, 114), color=OK, lw=1.1)
arrow((3, 114), (9, 121), OK, lw=1.1, ms=7)
txt(110, 9.8, "disconnect (COMM_LOST) → lease expiry → coordinated reclamation",
    5.2, OK, max_w=196, name="lease")

# --- geometric self-check: text fits, no box-border or arrow crossings -------
fig.canvas.draw()
inv = ax.transData.inverted()
EPS = 0.3   # pt tolerance: touching an edge within EPS is fine

def bbox_data(t):
    bb = t.get_window_extent(fig.canvas.get_renderer())
    (x0, y0) = inv.transform((bb.x0, bb.y0)); (x1, y1) = inv.transform((bb.x1, bb.y1))
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)

issues = 0
for t, max_w, name, owner in FITCHECK:
    x0, y0, x1, y1 = bbox_data(t)
    if x1 - x0 > max_w:
        print(f"[width] {name}: {x1-x0:.1f}pt > {max_w}pt", file=sys.stderr); issues += 1
    for bname, bx, by, bw, bh in BOXES:
        if bname == owner:      # its own box: text must stay fully inside
            if (x0 < bx - EPS or y0 < by - EPS or
                    x1 > bx + bw + EPS or y1 > by + bh + EPS):
                print(f"[contain] '{name}' escapes its box {bname!r}", file=sys.stderr)
                issues += 1
            continue
        ix0, iy0 = max(x0, bx), max(y0, by)
        ix1, iy1 = min(x1, bx + bw), min(y1, by + bh)
        if ix0 < ix1 - EPS and iy0 < iy1 - EPS:          # real intersection
            print(f"[text/box] '{name}' intersects {bname!r}", file=sys.stderr); issues += 1
    for sname, sx0, sy0, sx1, sy1 in SEGS:
        for k in range(51):                               # sample the segment
            u = k / 50
            px, py = sx0 + u * (sx1 - sx0), sy0 + u * (sy1 - sy0)
            if x0 - EPS < px < x1 + EPS and y0 - EPS < py < y1 + EPS:
                print(f"[text/arrow] '{name}' crossed by {sname}", file=sys.stderr)
                issues += 1; break
    if x0 < 0 or y0 < 0 or x1 > W or y1 > H:
        print(f"[canvas] '{name}' clipped", file=sys.stderr); issues += 1

print(f"self-check: {len(FITCHECK)} texts, {len(BOXES)} boxes, "
      f"{len(SEGS)} segments -> {issues} issue(s)")

out = Path(__file__).resolve().parent.parent / "paper" / "figs"
out.mkdir(parents=True, exist_ok=True)
fig.savefig(out / "fig1_arch.pdf")
fig.savefig(out / "fig1_arch.svg")
fig.savefig(out / "fig1_preview.png", dpi=300)
print(f"saved fig1_arch.pdf/.svg + preview -> {out}")
