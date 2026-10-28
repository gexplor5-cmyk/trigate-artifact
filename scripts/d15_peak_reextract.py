#!/usr/bin/env python3
"""D15: attack_rate_peak off-by-one 修复后全树重提
旧口径: substr(RSTART+10) 吃掉首位数字（ops_rate= 长 9 应 +9）
输出: results/D15_peak_reextract.csv (run, old_peak_from_raw_csv, new_peak, delta)
"""
import csv, glob, os, re, sys
OUT = "results/D15_peak_reextract.csv"
# 旧 raw csv 的 peak 列（R1F_raw.csv / R1G_raw.csv 第 17 列 attack_rate_peak）
old = {}
for f in ["results/R1F/R1F_raw.csv", "results/R1G/R1G_raw.csv"]:
    if not os.path.exists(f): continue
    for r in csv.DictReader(open(f)):
        rid = r.get("run_id") or r.get("RUN_ID")
        pk = r.get("attack_rate_peak") or r.get("PEAK")
        if rid: old[rid] = pk
rows = []
for log in sorted(glob.glob("results/*/**/attack.log", recursive=True)):
    run = os.path.basename(os.path.dirname(log))
    peak = 0
    for line in open(log, errors="replace"):
        m = re.search(r"ops_rate=(\d+)", line)
        if m: peak = max(peak, int(m.group(1)))
    rows.append((run, old.get(run, ""), peak))
with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["run_id", "old_peak(raw_csv)", "new_peak(fixed)"])
    w.writerows(rows)
# 汇总
peaks = [p for _, _, p in rows if p > 0]
print(f"total runs with attack.log: {len(rows)}; peaks>0: {len(peaks)}")
if peaks:
    print(f"new peak range: {min(peaks)}-{max(peaks)}")
    top = sorted(rows, key=lambda x: -x[2])[:5]
    for t in top: print(f"  TOP {t[0]}: {t[2]} (old={t[1]})")
