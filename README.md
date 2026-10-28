# TriGate Artifact

Artifact for the paper *"TriGate: Provable Per-Tenant Capacity Governance for E2
Subscriptions in the O-RAN near-RT RIC"* (anonymous submission).

TriGate is a layered admission-enforcement mechanism for the O-RAN E2 subscription
plane: three per-tenant upper bounds (scope, rate, standing state) enforced at the
earliest enforceable point (transport filter, pre-decode (sigma,rho) shaper,
application gate), with the E2 node as enforcement peer and lease-based reclamation.
This artifact contains the analysis-layer data, experiment/analysis scripts, the
FlexRIC patch set, and the trajectory datasets behind the paper's figures and tables.

## Contents

```
artifact/
├── data_key/        Aggregated per-campaign result tables (CSV) and analysis
│                    summaries (txt): ablations (R1B/R2E/D18), dose-response and
│                    metastability analysis (R3H/R3D), peer-enforcement runs,
│                    drive-window scan (R3PA), rho<mu arm (R3PB), escape-rate and
│                    EWS (early-warning) statistics, protocol-check outputs.
├── scripts/         Experiment queue scripts (run_*.sh, queue_*.sh), metric
│                    collection (collect_metrics.py), and all analysis scripts
│                    (analyze_*.py, r3_*.py) that regenerate every number in the
│                    paper from the raw per-run archives, plus figure scripts
│                    (make_figs.py, make_fig1.py, make_fig4_trajectories.py).
├── flexric_patch/   trigate_flexric.patch: the full patch set against FlexRIC
│                    v2.0.0 (L0 nftables/eBPF ruleset references, L1 pre-decode
│                    classifier + (sigma,rho) shaper, L2 gate, lease/peer state,
│                    and the seven defect fixes). extras/ holds untracked helper
│                    sources: attack/benign xApps, WCET probe, smoke-test scripts.
└── fig4_data/       Raw 10 Hz monitor.csv for the three trajectory runs shown in
                     the paper's trajectory figure (suppressed / diverged /
                     zero-input arms), see its README.
```

## Reproducing the analysis

1. Rebuild FlexRIC (if you want to re-run experiments):
   ```
   git clone --branch v2.0.0 --depth 1 --recursive https://github.com/duranta-project/flexric
   git apply trigate_flexric.patch       # from flexric_patch/
   # copy flexric_patch/extras/ sources into the corresponding FlexRIC locations
   apt install libsctp-dev libconfig-dev gcc-12 g++-12
   cmake with CC=gcc-12 and -DXAPP_MULTILANGUAGE=OFF; make -j && make install
   ```
2. Re-run an experiment family: `scripts/run_<family>.sh` (each writes per-run
   monitor CSV + logs into a results directory; edit the `RES`/workspace variables
   at the top of each script to point at your results root).
3. Regenerate analysis outputs: the `analyze_*.py` / `r3_*.py` scripts read the
   per-run CSVs and reproduce the statistics in the paper (Jeffreys intervals,
   drift fields, escape rates, EWS AUCs, Jain indices).
4. Regenerate the figures: `make_figs.py` (data figures), `make_fig1.py`
   (architecture diagram), `make_fig4_trajectories.py` (trajectory classes; reads
   `fig4_data/` directly and re-verifies the claims it plots via data assertions).

The raw per-run archives (about 2.3 GB: monitor CSVs, logs, protocol-checker
outputs for 625 runs) are not included for size reasons; aggregated tables in
`data_key/` are sufficient to re-derive every number in the paper. The raw
archives are available from the authors during review on request.

## Notes

- All experiment protocols were pre-registered (timestamped birth-chain files in
  `data_key/`, e.g. `V25_protocol_check.txt`, `R3PA_protocol.txt`,
  `R3PB_protocol.txt`).
- Two CVE candidate fixes are included in the patch (CVE-2026-37234
  disconnect-cleanup misroute; CVE-2026-37233 ID self-comparison); both were
  disclosed to the FlexRIC maintainers under coordinated disclosure practice.
- Code license: MIT (see LICENSE). Aggregated data: CC-BY-4.0.
