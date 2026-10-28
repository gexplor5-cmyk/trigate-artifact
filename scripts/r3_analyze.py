#!/usr/bin/env python3
# r3_analyze.py — R3B/R3C/R3D 收口分析：B11 判据核对+R3C 时间线 join+R3D 预言对照+前兆
import csv, os, math, sys
from scipy import stats
import numpy as np

W = "/root/trigate_ws/results"
P = lambda *a: print(*a)

# ================= R3B =================
if os.path.exists(f"{W}/R3B/R3B_raw.csv"):
    P("="*70); P("R3B B11 针对性触发收口（判据 P4/P5 核对）"); P("="*70)
    rows = [r for r in csv.DictReader(open(f"{W}/R3B/R3B_raw.csv"))]
    for r in rows:
        P(f"  {r['run_id']}: alive={r['ric']}/{r['agent']} b={r['b1']}/{r['b2']} ind={r['b1_ind']}/{r['b2_ind']} "
          f"fc_drop_lines={r['fc_drop']} full_rej_lines={r['full_rej']} l1={r['l1drop_pre']}->{r['l1drop_post']} "
          f"sub_fwd={r['sub_fwd']} cpu={r['cpu_mean']}")
    mal = [r for r in rows if r['arm'].startswith('malf')]
    if mal:
        fc1 = [r for r in mal if r['arm']=='malf_fc1']; fc0 = [r for r in mal if r['arm']=='malf_fc0']
        import statistics as st
        c1 = [float(r['cpu_mean']) for r in fc1]; c0 = [float(r['cpu_mean']) for r in fc0]
        P(f"  【H6】fc=1 CPU={c1}（med {st.median(c1) if c1 else 'NA'}） vs fc=0 CPU={c0}（med {st.median(c0) if c0 else 'NA'}）")
        P(f"  【P4】fc=1 臂 fc_drop 行>0：{all(int(r['fc_drop'])>0 for r in fc1) if fc1 else 'NA'}；良性存活+指示非零：{all(r['b1']=='1' and r['b2']=='1' and int(r['b1_ind'])>0 for r in mal)}")
    fills = {}
    for r in rows:
        if r['arm'].startswith('fill_'):
            fills.setdefault(r['arm'], []).append(r)
    if fills:
        P("  【P5】>32 关联 × FULLPOLICY 三臂（l1_drop 增量=fill 后 churn 期间）：")
        for arm, rs in sorted(fills.items()):
            for r in rs:
                P(f"    {r['run_id']}: full_rej_lines={r['full_rej']} l1 {r['l1drop_pre']}→{r['l1drop_post']} alive={r['ric']} ind={r['b1_ind']}/{r['b2_ind']}")
    trunc = [r for r in rows if r['arm']=='trunc_fix']
    if trunc:
        P(f"  【缺陷#7 修复验证】截断+关闭 {len(trunc)}/{len(trunc)} 存活：{[r['ric'] for r in trunc]}；短帧计数触发={all(int(r.get('fc_drop',0))>0 for r in trunc)}")

# ================= R3C =================
if os.path.exists(f"{W}/R3C/R3C_raw.csv"):
    P(); P("="*70); P("R3C b2/b1 误伤机制定案（探针+时间线）"); P("="*70)
    rows = [r for r in csv.DictReader(open(f"{W}/R3C/R3C_raw.csv"))]
    for r in rows:
        P(f"  {r['run_id']}: b2_ind={r['b2_ind']} slow_locks={r['lock_slow_n']} max_hold={r['lock_slow_max_us']}us ep_events={r['ep_events_n']} fd_peak={r['fd_peak']}")
    # 时间线 join：对每个 run，benign2 断流窗（5s 计数零增长窗）与锁事件密度对照
    import glob
    for rd in sorted(glob.glob(f"{W}/R3C/r3c_*")):
        run_id = os.path.basename(rd)
        b2log = f"{rd}/benign2.log"; mlog = f"{rd}/mutex_probe.log"
        if not (os.path.exists(b2log) and os.path.exists(mlog)): continue
        # b2 时间线
        tl = []
        for line in open(b2log, errors='ignore'):
            if 'indications total=' in line:
                try:
                    t = float(line.split('t=')[1].split('s')[0]); n = int(line.split('total=')[1].split()[0])
                    tl.append((t, n))
                except Exception: pass
        # 锁事件（L 行，时刻 us）
        lk = []
        for line in open(mlog, errors='ignore'):
            p = line.split()
            if p and p[0]=='L':
                try: lk.append((int(p[1])/1e6, int(p[2])))
                except Exception: pass
        if not tl or not lk: P(f"  {run_id}: 数据不足（tl={len(tl)} lk={len(lk)}）"); continue
        # 断流窗=相邻采样点增量 0 的区间
        gaps = []
        for i in range(1, len(tl)):
            if tl[i][1] == tl[i-1][1]:
                gaps.append((tl[i-1][0], tl[i][0]))
        t0 = tl[0][0]
        lk_t = [x[0]-t0 for x in lk]
        def dens(w0, w1): return sum(1 for t in lk_t if w0 <= t < w1)
        # 攻击窗 ≈ [11, 31]（与 R2C 同构：t=11 起攻击 20s）
        pre = dens(0, 9); atk = dens(11, 31); post = dens(33, 48)
        gap_in_atk = sum(1 for g0, g1 in gaps if g1 > 11 and g0 < 31)
        P(f"  {run_id}: b2 断流窗(攻击窗内)={gap_in_atk} 锁事件密度 pre/atk/post = {pre}/{atk}/{post} 次")

# ================= R3D =================
if os.path.exists(f"{W}/R3D/R3D_raw.csv"):
    P(); P("="*70); P("R3D 相变边界加密+滞后（附录 A 预言对照+R3F 前兆）"); P("="*70)
    rows = [r for r in csv.DictReader(open(f"{W}/R3D/R3D_raw.csv"))]
    pred = {20: 0.13, 24: 0.21, 28: 0.36}
    P("  【加密臂 vs 附录 A 预言】（预言 P 发散；实测=1-healthy 率）")
    from collections import defaultdict
    arm = defaultdict(list)
    for r in rows:
        if r['run_id'].startswith('r3d_cap'):
            c = int(r['run_id'].split('cap')[1].split('_')[0])
            h = 1 if (int(r['pendTO'])==0 and r['ric']=='1' and r['b1']=='1' and r['b2']=='1') else 0
            arm[c].append(h)
    for c in sorted(arm):
        hs = arm[c]; pdiv = 1 - sum(hs)/len(hs)
        P(f"    cap{c}: healthy {sum(hs)}/{len(hs)}，实测 P 发散={pdiv:.2f}，预言={pred.get(c,'NA')}")
    hs20 = arm.get(20, []); hs24 = arm.get(24, []); hs28 = arm.get(28, [])
    def rate(hs): return 1 - sum(hs)/len(hs) if hs else float('nan')
    P(f"  【H4 单调】P(20)={rate(hs20):.2f} ≥ P(24)={rate(hs24):.2f} ≥ P(28)={rate(hs28):.2f} → "
      f"{'成立' if rate(hs20)>=rate(hs24)>=rate(hs28) else '违例（如实入册）'}")
    P("  【滞后臂 H5】（T10→M30 vs M40 终态发散率；pendTO 终态 ≥1e5=发散）")
    hy = defaultdict(list)
    for r in rows:
        if r['run_id'].startswith('r3d_hys'):
            kind = 'T' if '_hys_T_' in r['run_id'] else 'M'
            c = int(r['run_id'].split('cap')[1].split('_')[0])
            div = 1 if int(r['pendTO']) >= 100000 else 0
            hy[(kind, c)].append((div, int(r['pendTO']), int(r['pendTO_mid'])))
    t_all = []
    for _k in (('T',24),('T',28),('T',32)):
        for _tup in hy.get(_k, []):
            t_all.append(_tup[0])
    m_all = []
    for _k in (('M',24),('M',28),('M',32)):
        for _tup in hy.get(_k, []):
            m_all.append(_tup[0])
    for kind in ('M', 'T'):
        for c in (24, 28, 32):
            v = hy.get((kind, c), [])
            if v: P(f"    {kind} cap{c}: 发散 {sum(d for d,_,_ in v)}/{len(v)} 终态 pendTO={[p for _,p,_ in v]} 相位中点 pendTO_mid={[pm for _,_,pm in v]}")
    if t_all and m_all:
        pv = stats.fisher_exact([[sum(t_all), len(t_all)-sum(t_all)], [sum(m_all), len(m_all)-sum(m_all)]], alternative='greater').pvalue
        P(f"  【H5】T 合并发散 {sum(t_all)}/{len(t_all)} vs M {sum(m_all)}/{len(m_all)}，Fisher 单侧 p={pv:.4f} → "
          f"{'滞后/自持成立' if pv<0.05 else '无差或反向（如实入册：无滞后，亚稳随机切换读法）'}")
    # R3F 前兆：10Hz CPU 方差/lag-1 自相关随 CAP
    P("  【R3F 前兆】攻击窗内 10Hz CPU 方差/lag-1 AC（1Hz 饱和结论复核）")
    for c in sorted(set(list(arm.keys()) + [24, 28, 32])):
        import glob as g
        runs = sorted(g.glob(f"{W}/R3D/r3d_cap{c}_rep*"))
        vs, acs = [], []
        for rd in runs:
            mon = f"{rd}/monitor.csv"
            if not os.path.exists(mon): continue
            try:
                rr = [r for r in csv.reader(open(mon)) if r and r[0] != 't']
                cpu = [float(r[1]) for r in rr if 11.0 <= float(r[0]) <= 31.0 and r[1] not in ('', 'DEAD')]
                if len(cpu) < 50: continue
                vs.append(np.var(cpu))
                x = np.array(cpu); acs.append(float(np.corrcoef(x[:-1], x[1:])[0, 1]))
            except Exception: pass
        if vs:
            import statistics as st
            P(f"    cap{c}: var med={st.median(vs):.1f}（n={len(vs)}） lag1AC med={st.median(acs):.3f}")

P("\n[r3_analyze 完成]")
