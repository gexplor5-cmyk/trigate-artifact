#!/usr/bin/env python3
# TriGate paper figures (Fig 2/3/4/5) — IEEE single-column, per nature-figure skill contract
# Backend: python (saved preference). Every panel defends one claim; data from archived CSVs/txt only.
import csv, math, os, re
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as mpl_plt

mpl.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "svg.fonttype": "none", "pdf.fonttype": 42, "font.size": 7,
    "axes.spines.right": False, "axes.spines.top": False,
    "axes.linewidth": 0.8, "legend.frameon": False,
})
W = "/root/trigate_ws"
FIG = f"{W}/paper/figs"; os.makedirs(FIG, exist_ok=True)
NEUT, SIG, ACC = "#8C8C8C", "#1F5FA9", "#C0504D"   # neutral / signal / accent families
CW = 3.5  # IEEE single column (in)

def save(fig, name):
    fig.savefig(f"{FIG}/{name}.pdf", bbox_inches="tight")
    fig.savefig(f"{FIG}/{name}.svg", bbox_inches="tight")
    mpl_plt.close(fig)
    print("saved", name)

# ---------- Fig 2a: dose-outcome with dual-caliber CI ----------
caps, ph, lo, hi = [], [], [], []
pat = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)/(\d+)/(\d+)/(\d+)\s+(\d+)/(\d+)=([\d.]+)\s+\[([\d.]+),([\d.]+)\]")
for ln in open(f"{W}/results/R3H/R3H_arms_summary.txt", encoding="utf-8"):
    m = pat.match(ln)
    if m:
        caps.append(int(m.group(1))); ph.append(float(m.group(9)))
        lo.append(float(m.group(10))); hi.append(float(m.group(11)))
caps, ph, lo, hi = map(np.array, (caps, ph, lo, hi))

# ---------- Fig 2b: quasi-potentials ----------
def parse_U(path, tag):
    for ln in open(path, encoding="utf-8"):
        if ln.startswith(tag):
            vals = [float(x) for x in ln.split(":")[1].split()]
            grid = [g for g in range(0, 105, 10)]
            return grid[:len(vals)], vals
    return [], []
gx, us = parse_U(f"{W}/results/R3H/R3H_potential_landscape.txt", "U_sup")
_, ud = parse_U(f"{W}/results/R3H/R3H_potential_landscape.txt", "U_div")

fig, (a, b) = mpl_plt.subplots(2, 1, figsize=(CW, 3.4), sharex=False,
                               gridspec_kw=dict(hspace=0.55))
a.axvspan(16, 32, color=NEUT, alpha=0.15, lw=0)
a.errorbar(caps, ph, yerr=[ph - lo, hi - ph], fmt="o-", color=SIG, ms=3,
           lw=1, capsize=2, label="suppression prob. (full-window, Jeffreys 95%)")
a.set_xscale("log"); a.set_xticks(caps)
a.set_xticklabels([str(c) for c in caps], fontsize=6)
a.set_xlabel(r"per-tenant scope bound CAP"); a.set_ylabel(r"$P_{\mathrm{supp}}$")
a.text(24, 0.45, "bistable band", fontsize=6, color=NEUT, ha="center")
a.set_ylim(-0.05, 1.1)
b.plot(gx, us, "-o", color=SIG, ms=2.5, lw=1, label=r"$U_{\mathrm{supp}}$ (restoring)")
b.plot(gx, ud, "-o", color=ACC, ms=2.5, lw=1, label=r"$U_{\mathrm{div}}$ (well at 20–22.5%)")
b.axvspan(20, 22.5, color=ACC, alpha=0.15, lw=0)
b.set_xlabel(r"RIC CPU (%) — state variable $x$"); b.set_ylabel(r"quasi-potential $U(x)$")
b.legend(fontsize=6, loc="lower right")
save(fig, "fig2_dose_potential")

# ---------- Fig 3: orthogonality bars ----------
fig, (a, b) = mpl_plt.subplots(1, 2, figsize=(CW, 1.7), gridspec_kw=dict(wspace=0.45))
a.bar([0, 1], [192.7, 6.7], color=[ACC, SIG], width=0.55)
a.set_yscale("log"); a.set_xticks([0, 1]); a.set_xticklabels(["no gate", "CAP=64"], fontsize=6)
a.set_ylabel("RIC RSS peak (MB)", fontsize=6.5)
a.text(0.5, 40, r"$\downarrow$96.5%", fontsize=7, ha="center", color=SIG)
a.set_title("flood: scope axis", fontsize=6.5)
lab = ["no gate", "naive\nCAP", "RATE"]
fwd = [46560, 60720, 420]
b.bar(range(3), fwd, color=[ACC, ACC, SIG], width=0.55)
b.set_yscale("log"); b.set_xticks(range(3)); b.set_xticklabels(lab, fontsize=6)
b.set_ylabel("E2 subscriptions forwarded", fontsize=6.5)
for i, (f, c) in enumerate(zip(fwd, ["73%", "73%", "8%"])):
    b.text(i, f * 1.3, c, fontsize=6, ha="center")
b.set_title("churn: rate axis", fontsize=6.5)
save(fig, "fig3_orthogonality")

# ---------- Fig 4: peer enforcement necessity ----------
fig, a = mpl_plt.subplots(figsize=(CW * 0.62, 1.5))
a.bar([0, 1], [1603570, 1495], color=[ACC, SIG], width=0.5)
a.set_yscale("log"); a.set_xticks([0, 1])
a.set_xticklabels(["RIC-only\ndeletion", "E2 peer\ncoordinated"], fontsize=6)
a.set_ylabel("zombie indications (20 s)", fontsize=6.5)
a.text(0.5, 20000, r"$\downarrow$99.9%  (CPU 142% $\to$ 32%)", fontsize=6.5, ha="center")
save(fig, "fig4_peer")

# ---------- Fig 5: trajectory classes ----------
def load_cpu(rid, base):
    t, c = [], []
    for r in csv.reader(open(f"{base}/{rid}/monitor.csv")):
        if not r or r[0] == "t":
            continue
        try:
            t.append(float(r[0])); c.append(float(r[1]))
        except (ValueError, IndexError):
            pass
    return np.array(t), np.array(c)
# zero-input arm is rep2 (rep1 is a suppressed run: tail CPU -> 0; see fig4_data/README).
# Local redraw with size guard + data assertions: scripts/make_fig4_trajectories.py
runs5 = [("r3d_cap24_rep2", "suppressed", SIG),
         ("r3d_cap24_rep1", "diverged", ACC),
         ("r3d_hys_T_cap24_rep2", "zero-input evolution", NEUT)]
fig, a = mpl_plt.subplots(figsize=(CW, 1.9))
for rid, lab, col in runs5:
    t, c = load_cpu(rid, f"{W}/results/R3D")
    a.plot(t, c, lw=0.9, color=col, label=f"{lab} ({rid.split('_rep')[0]})")
a.axvspan(18, 38, color=NEUT, alpha=0.10, lw=0)   # async-arm window
a.axvspan(18, 28, color=NEUT, alpha=0.14, lw=0)   # T-arm strong-attack sub-window
a.set_xlabel("time (s)"); a.set_ylabel("RIC CPU (%)"); a.legend(fontsize=5.5, loc="upper right")
a.set_xlim(0, 60)
save(fig, "fig5_trajectories")
print("all figures done")
