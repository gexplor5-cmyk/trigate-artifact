#!/usr/bin/env python3
"""R2-B 中期 sanity：逐 run 断言（防白做）——NaN/全零/离谱值检测"""
import csv, sys
f = "results/R2B/R2B_raw.csv"
rows = list(csv.DictReader(open(f)))
bad = []
for r in rows:
    rid = r['run_id']
    # 断言1：数值列非 NaN
    for k in ['delivered','peak','cpu_mean','cpu_trim','pendTO','b1_ind','b2_ind']:
        try: v = float(r.get(k,'0') or 0)
        except ValueError: bad.append(f"{rid}:{k}=NaN"); continue
    # 断言2：b1/b2 活着但 ind=0 且 RIC 活 → 可疑（订阅断流）
    if r['b1_alive']=='1' and r['ric_alive']=='1' and int(r['b1_ind'])==0 and int(r['b2_ind'])==0:
        bad.append(f"{rid}: 双良性 ind=0 但全活（订阅断流？）")
    # 断言3：cpu>400% 离谱
    if float(r.get('cpu_peak','0') or 0) > 400: bad.append(f"{rid}: cpu_peak>400%")
    # 断言4：闸门位置 sub_fwd 应受限
    pos = r['pos']
    if pos in ('ric_l2','l1l2','both') and int(r.get('sub_fwd',0)) > 400:
        bad.append(f"{rid}: {pos} 位置 sub_fwd={r['sub_fwd']} 超预期（闸门失效？）")
print(f"runs={len(rows)} 异常={len(bad)}")
for b in bad[:10]: print(" ", b)
