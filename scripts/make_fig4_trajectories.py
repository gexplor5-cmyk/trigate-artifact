#!/usr/bin/env python3
# Fig 4 (compiled figure number; file fig5_trajectories) — terminal trajectory classes.
# Standalone local redraw; reads fig4_data/ (copied from server results/R3D).
# Corrects the server render, whose output shipped 12.15 in tall (taller than the page)
# despite figsize=(3.5, 1.9), and the checklist's wrong gray run: the zero-input arm is
# r3d_hys_T_cap24_rep2 (rep1 is suppressed: tail CPU -> 0). See fig4_data/README_图4数据说明.md.
# Guard rails: data assertions (README claims re-checked against the CSVs) and an output
# MediaBox assertion so an oversized render can never ship silently again.
import csv
import re
import sys
from pathlib import Path

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt

mpl.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],  # match figs 2-5 / fig1
    "pdf.fonttype": 42, "svg.fonttype": "path",
})
NEUT, SIG, ACC = "#8C8C8C", "#1F5FA9", "#C0504D"   # same palette as make_figs.py

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "fig4_data"
OUT = ROOT / "paper" / "figs"

def load(run):
    with open(DATA / run / "monitor.csv", encoding="utf-8", errors="replace") as f:
        rows = list(csv.reader(f))[1:]          # first row is the header
    t, cpu, rss = [], [], []
    for r in rows:
        try:
            t.append(float(r[0])); cpu.append(float(r[1])); rss.append(float(r[2]) / 1024.0)  # KB -> MB
        except (ValueError, IndexError):
            pass
    return np.array(t), np.array(cpu), np.array(rss)

runs = {
    "suppressed": ("r3d_cap24_rep2", SIG),
    "diverged":   ("r3d_cap24_rep1", ACC),
    "zero-input": ("r3d_hys_T_cap24_rep2", NEUT),
}

# --- data assertions: the visual argument must be true in the data -----------------
t_b, cpu_b, rss_b = load("r3d_cap24_rep2")
t_r, cpu_r, rss_r = load("r3d_cap24_rep1")
t_g, cpu_g, rss_g = load("r3d_hys_T_cap24_rep2")

def check(name, cond, detail):
    print(f"  [{'ok' if cond else 'FAIL'}] {name}: {detail}")
    if not cond:
        sys.exit(f"data assertion failed: {name}")

check("suppressed tail ~0", cpu_b[t_b >= 25].mean() < 0.5, f"mean {cpu_b[t_b >= 25].mean():.2f}%")
check("diverged climbing", cpu_r[(t_r >= 30)].mean() > 8, f"t>=30 mean {cpu_r[t_r >= 30].mean():.1f}%")
check("zero-input plateau 8-11.5%", 8 <= cpu_g[t_g >= 60].mean() <= 11.5,
      f"t>=60 mean {cpu_g[t_g >= 60].mean():.1f}%")
check("zero-input RSS climbing", (np.diff(rss_g[t_g >= 28]) >= 0).mean() > 0.99,
      f"end {rss_g[-1]:.1f} MB, {((np.diff(rss_g[t_g >= 28]) >= 0).mean())*100:.0f}% steps up")
check("zero-input spans to ~74 s", 70 <= t_g[-1] <= 78, f"t_end {t_g[-1]:.1f} s")

# --- figure (designed at final print size: 3.5 x 2.0 in) ---------------------------
fig = plt.figure(figsize=(3.5, 2.0))
ax = fig.add_axes([0.115, 0.155, 0.765, 0.815])
axr = ax.twinx()

# two-tier attack shading: light = async-arm window 18-38 s; darker = T-arm strong 18-28 s
ax.axvspan(18, 38, color=NEUT, alpha=0.10, lw=0)
ax.axvspan(18, 28, color=NEUT, alpha=0.14, lw=0)
ax.text(23, 13.05, "strong\nattack", fontsize=4.8, color="#555555", ha="center", va="center",
        linespacing=1.1)
ax.text(33, 13.05, "async\nattack", fontsize=4.8, color="#555555", ha="center", va="center",
        linespacing=1.1)

for label, (rid, col) in runs.items():
    t, c, _ = load(rid)
    ax.plot(t, c, lw=0.9, color=col, label=label, solid_joinstyle="round")
axr.plot(t_g, rss_g, lw=0.8, color="#9A9A9A", ls=(0, (4, 2)))

ax.text(56, 12.55, "self-sustaining attractor", fontsize=4.8, color="#555555",
        style="italic", ha="center", va="center")

ax.set_xlim(0, 75); ax.set_ylim(0, 14)
axr.set_ylim(0, 40)
ax.set_xticks([0, 15, 30, 45, 60, 75]); ax.set_yticks([0, 3, 6, 9, 12])
axr.set_yticks([0, 10, 20, 30, 40])
ax.tick_params(labelsize=5.8, pad=1.5); axr.tick_params(labelsize=5.8, pad=1.5, colors="#777777")
ax.set_xlabel("time (s)", fontsize=6.3, labelpad=1.5)
ax.set_ylabel("RIC CPU (%)", fontsize=6.3, labelpad=1.5)
axr.set_ylabel("zero-input memory (MB)", fontsize=6.0, labelpad=2.5, color="#777777")
ax.legend(fontsize=5.4, loc="upper left", handlelength=1.4, handletextpad=0.5,
          borderpad=0.4, labelspacing=0.35, framealpha=0.9, edgecolor="#CCCCCC")

for a in (ax, axr):
    for s in a.spines.values():
        s.set_linewidth(0.6)

OUT.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT / "fig5_trajectories.pdf")
fig.savefig(OUT / "fig5_trajectories.svg")
fig.savefig(OUT / "fig5_preview.png", dpi=300)

# --- output guard: the shipped file must be single-column sized ---------------------
d = (OUT / "fig5_trajectories.pdf").read_bytes()
mb = re.search(rb"/MediaBox\s*\[([^\]]*)\]", d)
w, h = [float(x) for x in mb.group(1).split()][2:]
print(f"output MediaBox: {w:.1f} x {h:.1f} pt ({w/72:.2f} x {h/72:.2f} in)")
if not (240 <= w <= 260 and 130 <= h <= 220):
    sys.exit("output size guard FAILED — refusing to ship an oversized render")
print(f"saved fig5_trajectories.pdf/.svg + preview -> {OUT}")
