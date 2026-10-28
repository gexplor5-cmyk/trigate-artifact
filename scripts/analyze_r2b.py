#!/usr/bin/env python3
"""R2-B A 段重跑分析：三态（healthy/degraded/dead 扩维判据）× 位置 × Jeffreys CI + Fisher"""
import csv, math, sys
from collections import defaultdict
try:
    from scipy import stats
except ImportError:
    stats = None

W = "results/R2B"
rows = list(csv.DictReader(open(f"{W}/R2B_raw.csv")))
def tri(r):
    alive = int(r['ric_alive']) and int(r['agent_alive']) and int(r['b1_alive']) and int(r['b2_alive'])
    if not int(r['ric_alive']): return 'dead'
    if not (int(r['agent_alive']) and int(r['b1_alive']) and int(r['b2_alive'])): return 'collateral'  # RIC 活但良性死
    if int(r['pendTO']) > 0: return 'degraded'
    # [C12/B3-m7 修复 2026-10-20] 删除不可达分支 if not alive: return 'degraded'
    # （前面已按维度分支覆盖），保留语义等价的单出口
    return 'healthy'

agg = defaultdict(list)
for r in rows:
    agg[r['pos']].append(tri(r))

out = [["pos","n","healthy","degraded","collateral","dead","b1_ind_med","b2_ind_med","cpu_trim_med","healthy_CI95"]]
print(f"{'pos':10} {'n':>2} {'healthy':>7} {'degraded':>8} {'collateral':>10} {'dead':>4}  b1ind  b2ind  cpu_trim  healthy_JeffreysCI")
for pos in ['none','ric_l2','e2_only','both','ric_l1','l1l2']:
    ts = agg.get(pos, [])
    if not ts: continue
    h = ts.count('healthy'); d = ts.count('degraded'); c = ts.count('collateral'); dd = ts.count('dead')
    n = len(ts)
    sub = [r for r in rows if r['pos']==pos]
    import statistics as st
    b1 = st.median(int(r['b1_ind']) for r in sub); b2 = st.median(int(r['b2_ind']) for r in sub)
    cpu = st.median(float(r['cpu_trim']) for r in sub)
    ci = ""
    if stats and n>0:
        lo,hi = stats.beta.ppf([0.025,0.975], h+0.5, n-h+0.5)
        ci = f"[{lo:.3f},{hi:.3f}]{'✓' if lo>0.5 else '✗跨0.5'}"
    print(f"{pos:10} {n:>2} {h:>7} {d:>8} {c:>10} {dd:>4}  {b1:>5}  {b2:>5}  {cpu:>7.1f}  {ci}")
    out.append([pos,n,h,d,c,dd,b1,b2,cpu,ci])

with open(f"{W}/R2B_summary.csv","w",newline="") as f:
    csv.writer(f).writerows(out)

# 核心句判定（A8 事前判据）
if stats:
    l1l2 = agg.get('l1l2', []); h = l1l2.count('healthy'); n = len(l1l2)
    ctrl_ok = all(agg.get(p,[]).count('healthy') <= n*0.5 for p in ['none','ric_l2','e2_only','both','ric_l1'] if agg.get(p))
    if n:
        lo,hi = stats.beta.ppf([0.025,0.975], h+0.5, n-h+0.5)
        verdict = "✓ 可写「唯一 healthy」" if (lo>0.5 and ctrl_ok) else "✗ 不可写——按预案降级为方向性表述"
        print(f"\n核心句判定：l1l2 healthy={h}/{n} CI=[{lo:.3f},{hi:.3f}] 对照全≤半数={ctrl_ok} → {verdict}")
