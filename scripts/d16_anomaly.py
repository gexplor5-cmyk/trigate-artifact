#!/usr/bin/env python3
"""D16/D17 反常归因（离线）：
D16: r100(平滑) vs r1000(突发) 同 delivered 下三态翻转机理——
     攻击器逐秒到达序列 CV + RIC 逐秒 CPU 曲线 + 忙期结构
D17: e2_only/both CPU≈none 两倍——REFUSE 回包量（ric_tail failure response 计数）×CPU 对齐
"""
import csv, re, sys, statistics as st

def load_attack_series(path):
    """逐秒 (subs+dels) 序列（attack.log 的 t=x.x subs=... 行）与 ops_rate 序列"""
    t, cum, rates = [], [], []
    last = {}
    for line in open(path, errors="replace"):
        m = re.match(r"\[async\] t=([\d.]+)s subs=(\d+) dels=(\d+).*ops_rate=(\d+)", line)
        if m:
            t.append(float(m.group(1)))
            cum.append(int(m.group(2)) + int(m.group(3)))
            rates.append(int(m.group(4)))
    # 逐秒增量
    inc = []
    for i in range(1, len(cum)):
        inc.append(cum[i] - cum[i-1])
    return t, inc, rates

def load_cpu(path):
    rows = [r for r in csv.reader(open(path)) if r and r[0] != "t"]
    return [(float(r[0]), float(r[1])) for r in rows if len(r) > 1 and r[1] != ""]

def cv(xs):
    return (st.pstdev(xs) / st.mean(xs)) if xs and st.mean(xs) > 0 else 0

print("=== D16: r100 vs r1000 baseline（同 delivered 档）===")
for run in ["f2_r100_baseline_rep1", "f2_r100_baseline_rep2", "f2_r1000_baseline_rep1", "f2_r1000_baseline_rep2"]:
    try:
        t, inc, rates = load_attack_series(f"results/R1F/{run}/attack.log")
        cpu = load_cpu(f"results/R1F/{run}/monitor.csv")
        w = [(tt, c) for tt, c in cpu if tt >= 11]
        cpus = [c for _, c in w]
        # 忙期结构：CPU>50% 的连续段数
        busy = 0; prev_hi = False
        for c in cpus:
            hi = c > 50
            if hi and not prev_hi: busy += 1
            prev_hi = hi
        print(f"{run}: 到达CV={cv(inc):.2f} 增量min/max={min(inc) if inc else 0}/{max(inc) if inc else 0} "
              f"| CPU mean={st.mean(cpus) if cpus else 0:.0f}% peak={max(cpus) if cpus else 0:.0f}% "
              f"| >50%忙期段数={busy} 样本n={len(cpus)}")
    except FileNotFoundError:
        print(f"{run}: MISSING")

print()
print("=== D17: e2_only/both vs none CPU + REFUSE 回包 ===")
# R1G c3 段（强制位置）: g_churn_{none,e2_only,both} 的 ric_tail REFUSE 计数
for run in sorted(__import__("glob").glob("results/R1G/g_churn_*_rep1")):
    name = run.split("/")[-1]
    try:
        ric = open(f"{run}/ric_tail.log", errors="replace").read()
        e2r = 0
        try:
            ag = open(f"{run}/agent_tail.log", errors="replace").read()
            m = re.findall(r"REFUSE \(累计 (\d+)\)", ag)
            e2r = int(m[-1]) if m else 0
        except FileNotFoundError:
            pass
        cpu = load_cpu(f"{run}/monitor.csv")
        w = [c for tt, c in cpu if tt >= 11]
        print(f"{name}: CPU mean={st.mean(w) if w else 0:.0f}% | E2 REFUSE cum={e2r} | [iApp] RESPONSE tx={ric.count('RESPONSE tx')}")
    except Exception as e:
        print(f"{name}: ERR {e}")
