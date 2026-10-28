#!/usr/bin/env python3
"""R1G 汇总分析：位置矩阵三态口径 + L1 判据 + 补丁前后对照
三态：healthy(alive 且 0 pending 超时) / degraded(alive 且>0) / dead
对照：R1B 原始（补丁前）同格存活率
"""
import csv, os, re
from collections import defaultdict

RES = "/root/trigate_ws/results/R1G"
R1B = "/root/trigate_ws/results/R1B"

def ric_stats(rd):
    p = f"{RES}/{rd}/ric_tail.log"
    if not os.path.exists(p): return None, None, None
    txt = open(p, errors="ignore").read()
    pt = len(re.findall(r"Pending event timeout", txt))
    m = re.findall(r"Assertion.*failed", txt)
    return pt, (m[-1][:60] if m else None), len(re.findall(r"过期 DELETE", txt))

def r1b_cell(alive_runs):
    return f"{sum(alive_runs)}/{len(alive_runs)}"

def main():
    rows = list(csv.DictReader(open(f"{RES}/R1G_raw.csv")))
    out = []
    for r in rows:
        pt, fatal, stale = ric_stats(r["run_id"])
        pt = pt or 0
        state = "dead" if r["ric_alive"] == "0" else ("degraded" if pt > 0 else "healthy")
        out.append(dict(run_id=r["run_id"], seg=r["seg"], attacker=r["attacker"],
                        pos=r["pos"], rep=r["rep"], state=state,
                        ric_alive=r["ric_alive"], agent_alive=r["agent_alive"],
                        pending_timeouts=pt, fatal_assert=fatal or "",
                        stale_del_skipped=stale or 0,
                        benign_sub_ok=r["benign_sub_ok"],
                        benign_ind_during=r["benign_ind_during"],
                        l1_dropped=r["l1_dropped"], l2_refuse_gate=r["l2_refuse_gate"],
                        e2_refuse_cum=r["e2_refuse_cum"], sub_fwd=r["sub_fwd"],
                        delivered=r["delivered"], cpu_mean=r["ric_cpu_mean"],
                        cpu_peak=r["ric_cpu_peak"]))
    with open(f"{RES}/R1G_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)
    agg = defaultdict(list)
    for o in out:
        agg[(o["seg"], o["attacker"], o["pos"])].append(o)
    print(f"{'seg':3s} {'attacker':6s} {'pos':8s} {'states':30s} {'deliv':16s} {'cpu':14s} {'l1drop':8s} {'benign_ind':12s}")
    for k in sorted(agg):
        v = agg[k]
        states = "/".join(o["state"][:4] for o in v)
        dl = "/".join(o["delivered"] for o in v)
        cpu = "/".join(o["cpu_mean"] for o in v)
        l1 = "/".join(o["l1_dropped"] for o in v)
        bi = "/".join(o["benign_ind_during"] for o in v)
        print(f"{k[0]:3s} {k[1]:6s} {k[2]:8s} {states:30s} {dl:16s} {cpu:14s} {l1:8s} {bi:12s}")
    # C 段与 R1B 补丁前对照
    print("\n--- C 段补丁前后对照（R1B 原 n=3 → R1G 新 n=3）---")
    r1b = {}
    for r in csv.DictReader(open(f"{R1B}/R1B_metrics.csv")):
        r1b.setdefault((r["attacker"], int(r["cap"]), int(r["rate"]), int(r["state"])),
                       []).append(int(r["ric_alive"]))
    mapping = {
        "g2_flood_c16_r10_s1024": ("flood", 16, 10, 1024),
        "g2_flood_c64_r10_s0": ("flood", 64, 10, 0),
        "g2_flood_c256_r10_s0": ("flood", 256, 10, 0),
        "g2_flood_c256_r100_s0": ("flood", 256, 100, 0),
        "g2_churn_c0_r0_s0": ("churn", 0, 0, 0),
    }
    for o in out:
        if o["seg"] != "C": continue
        pre = "NA"
        for pref, key in mapping.items():
            if o["run_id"].startswith(pref):
                pre = r1b_cell(r1b.get(key, []))
                break
        print(f"{o['run_id']:32s} 补丁前 {pre:5s} → 补丁后 {o['state']:9s} pendTO={o['pending_timeouts']} fatal={o['fatal_assert'] or '无'}")

if __name__ == "__main__":
    main()
