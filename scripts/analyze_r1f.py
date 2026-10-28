#!/usr/bin/env python3
"""R1F 汇总分析：C1/B-C2 修复后的高速率档结论重标
三态结局口径（修复后新增）：
  healthy = alive 且 pending_timeout==0（E2 通信全程未丢失）
  degraded = alive 且 pending_timeout>0（E2 通信反复丢失——旧代码首个即崩）
  dead
offered-load 口径（B-C2）：delivered = sent_total - sndfail（流控丢弃显式计量）
"""
import csv, os, re

RES = "/root/trigate_ws/results/R1F"

def pending_timeouts(rd):
    p = f"{RES}/{rd}/ric_tail.log"
    if not os.path.exists(p): return None
    txt = open(p, errors="ignore").read()
    return len(re.findall(r"Pending event timeout", txt))

def patch_skips(rd):
    p = f"{RES}/{rd}/ric_tail.log"
    if not os.path.exists(p): return None
    txt = open(p, errors="ignore").read()
    return len(re.findall(r"consume_fd 无效|孤儿事件|短读", txt))

def main():
    rows = list(csv.DictReader(open(f"{RES}/R1F_raw.csv")))
    out = []
    for r in rows:
        pt = pending_timeouts(r["run_id"]) or 0
        ps = patch_skips(r["run_id"]) or 0
        state = ("dead" if r["ric_alive"] == "0"
                 else "degraded" if pt > 0 else "healthy")
        out.append(dict(run_id=r["run_id"], rate=r["rate"], gate=r["gate"], rep=r["rep"],
                        state=state, ric_alive=r["ric_alive"],
                        pending_timeouts=pt, patched_crash_skips=ps,
                        sub_fwd=r["sub_fwd_cnt"], refuse=r["refuse_cnt"],
                        sent=r["sent_total"], sndfail=r["sndfail"],
                        delivered=r["delivered"], dur_s=r["dur_at_done"],
                        ceiling_hit=r["ceiling_hit"], peak=r["attack_rate_peak"],
                        cpu_mean=r["ric_cpu_mean"], cpu_peak=r["ric_cpu_peak"]))
    with open(f"{RES}/R1F_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)
    # 聚合
    from collections import defaultdict
    agg = defaultdict(list)
    for o in out:
        agg[(o["rate"], o["gate"])].append(o)
    print(f"{'cell':24s} {'state':18s} {'deliv':>7s} {'subfwd':>7s} {'cpu':>6s} {'pendTO':>7s}")
    for k in sorted(agg, key=lambda x: (int(x[0]), x[1])):
        v = agg[k]
        states = "/".join(o["state"] for o in v)
        dl = "/".join(o["delivered"] for o in v)
        sf = "/".join(o["sub_fwd"] for o in v)
        cpu = "/".join(o["cpu_mean"] for o in v)
        pt = "/".join(str(o["pending_timeouts"]) for o in v)
        print(f"{k[0]+'_'+k[1]:24s} {states:18s} {dl:>7s} {sf:>7s} {cpu:>6s} {pt:>7s}")

if __name__ == "__main__":
    main()
