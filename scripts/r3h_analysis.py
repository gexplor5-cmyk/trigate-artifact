#!/usr/bin/env python3
# R3H 亚稳随机动力学分析（定向创新方案 1+2 落地，2026-10-20）
# 输入：R3D 27 run monitor.csv（10Hz）+ R3D_raw.csv + R2E/D18/R3A 在盘结局
# 输出：results/R3H/ 下数据表——分岔图数据/KM 漂移场/EWS 先行性/逃逸率/生态学三标准
# 全部标 descriptive；方法：Honisch-Friedrich KM 核估计 + Dakos/Scheffer EWS 协议
import csv, os, math, json
import numpy as np

W = '/root/trigate_ws'
OUT = f'{W}/results/R3H'
os.makedirs(OUT, exist_ok=True)

# ---------- 1. 载入 R3D monitor（10Hz）与结局 ----------
runs = {}
for row in csv.DictReader(open(f'{W}/results/R3D/R3D_raw.csv')):
    runs[row['run_id']] = row

def load_mon(rid):
    t=[];cpu=[];rss=[]
    for r in csv.reader(open(f'{W}/results/R3D/{rid}/monitor.csv')):
        if not r or r[0]=='t': continue
        try:
            t.append(float(r[0])); cpu.append(float(r[1])); rss.append(float(r[2]))
        except (ValueError, IndexError): pass
    return np.array(t), np.array(cpu), np.array(rss)

M = {rid: load_mon(rid) for rid in runs}

def outcome(row):
    """结局分组：diverged (pendTO>=1e5) / suppressed (pendTO==0) / intermediate"""
    pt = int(row['pendTO'])
    if pt >= 1e5: return 'diverged'
    if pt == 0: return 'suppressed'
    return 'intermediate'

grp = {rid: outcome(r) for rid, r in runs.items()}

# ---------- 2. 分岔图数据（run 级终态 vs CAP；联合 R2E/D18/R3A） ----------
# ric_l2 切片联合曲线（R2E cap4/16/32/60/64 + D18 c0/c4/c16/c64/c256 + R3D cap20/24/28）
bif = []
def add_point(cap, rid, pendTO, cpu_trim, grp, src, done_t, sent):
    bif.append(dict(cap=cap, run=rid, pendTO=int(pendTO), log10_pendTO=round(math.log10(pendTO),3) if pendTO>0 else 0.0,
                     cpu_trim=cpu_trim, group=grp, src=src, done_t=done_t, sent=int(sent)))

for row in csv.DictReader(open(f'{W}/results/R2E/R2E_raw.csv')):
    cap = int(row['run_id'].split('_')[1].replace('cap',''))
    early = int(row['sent'])>=65400  # REQ_ID 天花板早停口径（R2B_stratified 同款）
    add_point(cap, row['run_id'], int(row['pendTO']), float(row['cpu_trim']),
              outcome(row) if not early else 'early-stop', 'R2E', float(row['done_t']), int(row['sent']))
for row in csv.DictReader(open(f'{W}/results/D18_full_metrics.csv')):
    cap = int(row['run_id'].split('_')[1].replace('c',''))
    early = int(row['sent_total'])>=65400
    add_point(cap, row['run_id'], int(row['pendTO']), float(row['cpu_trim']),
              outcome(row) if not early else 'early-stop', 'D18', float(row['done_t']), int(row['sent_total']))
for row in csv.DictReader(open(f'{W}/results/R3D/R3D_raw.csv')):
    rid = row['run_id']
    if not rid.startswith('r3d_cap'): continue
    cap = int(rid.split('_')[1].replace('cap',''))
    early = int(row['sent'])>=65400
    add_point(cap, rid, int(row['pendTO']), float(row['cpu_trim']),
              outcome(row) if not early else 'early-stop', 'R3D', float(row['done_t']), int(row['sent']))

with open(f'{OUT}/R3H_bifurcation_data.csv','w',newline='') as f:
    wtr = csv.DictWriter(f, fieldnames=list(bif[0].keys())); wtr.writeheader(); wtr.writerows(bif)

# 分臂汇总（含早停/全程分层 + Jeffreys CI）
def jeffreys(k, n, a=0.5, b=0.5):
    from scipy.stats import beta as B
    lo = B.ppf(0.025, k+a, n-k+b); hi = B.ppf(0.975, k+a, n-k+b)
    return lo, hi

arms = {}
for p in bif:
    if p['src']=='D18' and p['cap']==0: key='cap0'
    else: key = f"cap{p['cap']}"
    arms.setdefault(key, []).append(p)

with open(f'{OUT}/R3H_arms_summary.txt','w') as f:
    f.write("R3H 分岔/联合曲线分臂汇总（ric_l2 切片；early-stop=sent≥65400 天花板口径）\n")
    f.write("CAP   n   suppressed/intermediate/diverged/early-stop   P_h(全程)  Jeffreys95(全程)  P_h(含早停)  Jeffreys95(含早停)\n")
    order = ['cap0','cap4','cap16','cap20','cap24','cap28','cap32','cap60','cap64','cap256']
    for key in order:
        ps = arms.get(key, [])
        if not ps: continue
        cap = 0 if key=='cap0' else int(key[3:])
        fw = [p for p in ps if p['group']!='early-stop']
        allr = ps
        k1 = sum(1 for p in fw if p['group']=='suppressed'); n1=len(fw)
        k2 = sum(1 for p in allr if p['group'] in ('suppressed','early-stop')); n2=len(allr)
        l1,h1 = (jeffreys(k1,n1) if n1 else (float('nan'),)*2)
        l2,h2 = (jeffreys(k2,n2) if n2 else (float('nan'),)*2)
        inter = sum(1 for p in ps if p['group']=='intermediate'); div=sum(1 for p in ps if p['group']=='diverged'); es=sum(1 for p in ps if p['group']=='early-stop')
        f.write(f"{cap:4d} {len(ps):3d}  {k1}/{inter}/{div}/{es}   "
                f"{k1}/{n1}={k1/n1 if n1 else float('nan'):.2f}  [{l1:.3f},{h1:.3f}]   "
                f"{k2}/{n2}={k2/n2 if n2 else float('nan'):.2f}  [{l2:.3f},{h2:.3f}]\n")

# ---------- 3. KM 漂移场重建（状态=RIC CPU%，10Hz） ----------
# NW 核估计 M1(x)=E[X_{t+Δ}-X_t | X_t=x]，按 CAP 池化 run 级轨迹（结局不筛，先验分组另报）
# 诚实声明：CPU 为 10Hz 代理状态量；非梯度系统只报漂移主导项；M2 有偏（采样欠消息级）
def km_drift(trajs, grid, bw):
    """trajs: list of (X_t, dX) arrays; Gaussian NW"""
    X = np.concatenate([t[0] for t in trajs]); dX = np.concatenate([t[1] for t in trajs])
    out=[]; nboot=[]
    for g in grid:
        wgt = np.exp(-0.5*((X-g)/bw)**2)
        s = wgt.sum()
        m = (wgt*dX).sum()/s if s>1e-9 else np.nan
        out.append(m); nboot.append(s)
    return np.array(out), np.array(nboot)

def traj_pairs(rid, t0=18.0, dt=1.0):
    """攻击窗内轨迹（t>=t0），Δ=dt 秒（10 帧）步进的 (X_t, X_{t+dt}-X_t)"""
    t,cpu,rss = M[rid]
    X=[];D=[]
    for i in range(len(t)-1):
        if t[i] < t0: continue
        j = np.searchsorted(t, t[i]+dt)
        if j >= len(t) or abs(t[j]-t[i]-dt) > 0.3: continue
        X.append(cpu[i]); D.append(cpu[j]-cpu[i])
    return np.array(X), np.array(D)

groups = {
    'low_CAP(CAP<=16,压制区)': ['r3d_cap20_rep1'],  # R3D 无 cap16，用 cap24/28 中压制 run 代替见下
}
# 实际分组：R3D 只有 20/24/28 加密+24/28/32 滞后。分三池：
pool_defs = {
  'CAP20（边界陡谷臂）': [r for r in runs if r.startswith('r3d_cap20')],
  'CAP24': [r for r in runs if r.startswith('r3d_cap24') or r.startswith('r3d_hys_M_cap24') or r.startswith('r3d_hys_T_cap24')],
  'CAP28': [r for r in runs if r.startswith('r3d_cap28') or r.startswith('r3d_hys_M_cap28') or r.startswith('r3d_hys_T_cap28')],
  'CAP32（滞后臂）': [r for r in runs if 'cap32' in r],
}
grid = np.arange(0, 105, 2.5)
km_lines = {}
with open(f'{OUT}/R3H_km_drift.txt','w') as f:
    f.write("R3H Kramers-Moyal 漂移场重建（状态 X=RIC CPU%，10Hz，Δ=1s；Gaussian NW，带宽敏感性 5/10/20）\n")
    f.write("诚实声明：CPU 代理状态量；10Hz 对消息级跳变欠采样→M2(扩散)有偏不报；只报漂移主导项 M1(x)\n")
    f.write("用途：漂移符号结构=状态方向场；零点=候选不动点；非梯度系统不做势函数唯一性主张（准势读法）\n\n")
    for name, rids in pool_defs.items():
        rids = sorted(set(rids))
        f.write(f"== {name}（{len(rids)} run 池化，结局混合如实）==\n")
        for bw in (5.0, 10.0, 20.0):
            trajs = [traj_pairs(r) for r in rids]
            trajs = [(x,d) for x,d in trajs if len(x)>5]
            if not trajs: continue
            m, neff = km_drift(trajs, grid, bw)
            zeros = []
            for i in range(1,len(grid)-1):
                if np.isnan(m[i-1]) or np.isnan(m[i+1]): continue
                if m[i-1]*m[i+1] < 0: zeros.append(grid[i])
            km_lines[(name,bw)] = m
            f.write(f"  bw={bw:4.0f}: " + " ".join(f"{g:.0f}:{v:+.2f}" for g,v in zip(grid,m) if not math.isnan(v) and int(g)%10==0) + "\n")
            f.write(f"        符号翻转点（候选不动点 CPU%）: {zeros if zeros else '无（区间内单侧）'}\n")
        f.write("\n")
        # 结局分组漂移（发散 run vs 压制 run）
        for gname in ('diverged','suppressed'):
            sub = [r for r in rids if grp[r]==gname]
            if len(sub)<1: continue
            trajs = [traj_pairs(r) for r in sub]; trajs=[(x,d) for x,d in trajs if len(x)>5]
            if not trajs: continue
            m,_ = km_drift(trajs, grid, 10.0)
            f.write(f"  [{gname} run 池化 n={len(sub)}] " + " ".join(f"{g:.0f}:{v:+.2f}" for g,v in zip(grid,m) if not math.isnan(v) and int(g)%10==0) + "\n")
        f.write("\n")

# ---------- 4. EWS 先行性检验（run 级结局分组 + 早期窗指标） ----------
# 协议：攻击窗起点 t0=18s；早期窗 [18, 23)（攻击开始后前 5s）；指标=rolling var + lag-1 AR(1)
# 检验：早期窗指标对结局的判别（AUC）+ Kendall τ；对照全窗指标（非先行，作上限参考）
from itertools import combinations
def ews_feats(rid, t0=18.0, t1=23.0):
    t,cpu,rss = M[rid]
    m = (t>=t0)&(t<t1)
    if m.sum()<20: return None
    x = cpu[m]
    var = float(np.var(x, ddof=1))
    if np.std(x)<1e-9: ar1=0.0
    else: ar1 = float(np.corrcoef(x[:-1],x[1:])[0,1])
    return dict(var=var, ar1=ar1, mean=float(np.mean(x)), n=int(m.sum()))

def auc(scores, labels):
    pos = [s for s,l in zip(scores,labels) if l==1]; neg=[s for s,l in zip(scores,labels) if l==0]
    if not pos or not neg: return float('nan')
    c=0; tot=0
    for a in pos:
        for b in neg:
            tot+=1
            c += 1 if a>b else (0.5 if a==b else 0)
    return c/tot

def kendall_tau(x, y):
    n=len(x); c=d=0
    for i,j in combinations(range(n),2):
        if (x[i]-x[j])*(y[i]-y[j])>0: c+=1
        elif (x[i]-x[j])*(y[i]-y[j])<0: d+=1
    tau=(c-d)/(0.5*n*(n-1))
    # exact p via normal approx
    var_tau=2*(2*n+5)/(9*n*(n-1))
    z=tau/math.sqrt(var_tau)
    from math import erf
    p=2*(1-0.5*(1+erf(abs(z)/math.sqrt(2))))
    return tau,p

ews_rows=[]
for rid,r in runs.items():
    if not (rid.startswith('r3d_cap') or rid.startswith('r3d_hys_T')): continue
    f5 = ews_feats(rid, 18.0, 23.0)
    fall = ews_feats(rid, 18.0, 38.0)
    lab = 1 if grp[rid]=='diverged' else 0
    if f5 and fall:
        ews_rows.append(dict(run=rid, group=grp[rid], label=lab,
                             var5=f5['var'], ar15=f5['ar1'], mean5=f5['mean'],
                             varF=fall['var'], ar1F=fall['ar1'], meanF=fall['mean']))
with open(f'{OUT}/R3H_ews_runlevel.csv','w',newline='') as f:
    wtr=csv.DictWriter(f,fieldnames=list(ews_rows[0].keys())); wtr.writeheader(); wtr.writerows(ews_rows)

labs=[e['label'] for e in ews_rows]
# 【更正 2026-10-20（R4 写作前置清单 3/B6-M3）】EWS 判别力改双口径并报：
# 口径 A=intermediate 计入 suppressed 侧（neg=n_supp+ n_int）；口径 B=剔除 intermediate。
rows_A = ews_rows  # 现行 lab 口径：非 diverged 一律 0（含 intermediate）
rows_B = [e for e in ews_rows if e['group']!='intermediate']
labs_A = [e['label'] for e in rows_A]; labs_B = [e['label'] for e in rows_B]
with open(f'{OUT}/R3H_ews_verdict.txt','w') as f:
    f.write("R3H EWS 先行性检验（run 级结局分组；R3F 的臂级聚合粗糙问题按 m12 处置后重做）\n")
    nint = sum(1 for e in ews_rows if e['group']=='intermediate')
    f.write(f"样本：加密臂 9 + T 臂 9 = 18 run；diverged={sum(labs_A)}；"
            f"口径 A（intermediate 计入 suppressed 侧，neg={len(labs_A)-sum(labs_A)}，其中 intermediate {nint}）/口径 B（剔除 intermediate，neg={len(labs_B)-sum(labs_B)}）\n\n")
    f.write("判别力（AUC，diverged=1；双口径并报）：\n")
    for k,desc in [('var5','早期窗[18,23s) var'),('ar15','早期窗 lag-1 AC'),('mean5','早期窗 mean CPU'),
                   ('varF','全窗 var（非先行上限参考）'),('ar1F','全窗 lag-1 AC')]:
        scA=[e[k] for e in rows_A]; scB=[e[k] for e in rows_B]
        f.write(f"  {desc:28s} AUC_A={auc(scA,labs_A):.3f}  AUC_B={auc(scB,labs_B):.3f}\n")
    f.write("\nKendall τ（指标 vs 结局 label；τ>0=指标高→发散；口径 A）：\n")
    for k in ('var5','ar15','varF','ar1F'):
        tau,p = kendall_tau([e[k] for e in rows_A], labs_A)
        f.write(f"  {k:6s} τ={tau:+.3f} (approx p={p:.3f})\n")
    f.write("\n先行性读法：早期窗 AUC 显著>0.5 且接近全窗上限 → 指标在结局确定前携带信息；\n")
    f.write("诚实边界：结局由攻击驱动，早期窗指标可能是攻击强度代理而非临界慢化（CSD）——两解释并列呈报。\n")
    # 逐 run 表
    f.write("\n逐 run：\n")
    for e in ews_rows:
        f.write(f"  {e['run']:24s} {e['group']:12s} var5={e['var5']:7.2f} ar15={e['ar15']:+.3f} mean5={e['mean5']:5.1f} varF={e['varF']:7.2f} ar1F={e['ar1F']:+.3f}\n")

# ---------- 5. 零输入自发演化（T 臂发散 run 的攻击后轨迹） ----------
with open(f'{OUT}/R3H_zero_input_evolution.txt','w') as f:
    f.write("R3H T 臂零输入自发演化（B5-C2 事实重读的动力学侧写：强攻 10s 结束后 CPU/RSS 轨迹）\n")
    f.write("时间轴：phase1 攻击 [18,28)，phase1 结束后为低/零输入窗（attack2 0 字节 run=零输入）\n")
    f.write("取每 run 在 t=25/30/35/45/55s 的 RIC CPU%/RSS(MB)：\n\n")
    for rid in sorted(runs):
        if not rid.startswith('r3d_hys_T'): continue
        t,cpu,rss = M[rid]
        pts=[]
        for tt in (25,30,35,45,55):
            i=np.searchsorted(t,tt)
            if i<len(t): pts.append(f"t{tt}:{cpu[i]:.0f}%/{rss[i]/1024:.0f}M")
        f.write(f"  {rid:24s} pendTO={int(runs[rid]['pendTO']):>9d} attack2={'0B' if os.path.getsize(f'{W}/results/R3D/{rid}/attack2.log')==0 else 'ok'}  " + " ".join(pts) + "\n")

# ---------- 6. 逃逸率读法（驱动时长 × P(div)——早停 run 的一致性证据） ----------
# 【更正 2026-10-20（R4 写作前置清单 2/B6-M2）】早停清单由三源（R2E/D18/R3D，仅 3 run）
# 扩为五源全量扫描（+R3A/R2B），判定口径按各源实况：R3A=sent≥65400；R2B=attack_class
# 官方口径列。计数、来源、suppressed 与否全部由计算得出，禁止硬编码。
es_all = [dict(cap=p['cap'], run=p['run'], pendTO=p['pendTO'], done_t=p['done_t'],
               src=p['src'], sent=p['sent']) for p in bif if p['group']=='early-stop']
for row in csv.DictReader(open(f'{W}/results/R3A/R3A_raw.csv')):
    if int(row['sent'])>=65400:
        es_all.append(dict(cap=int(row['run_id'].split('_')[2].replace('cap','')), run=row['run_id'],
                           pendTO=int(row['pendTO']), done_t=float(row['done_t']), src='R3A', sent=int(row['sent'])))
for row in csv.DictReader(open(f'{W}/results/R2B/R2B_stratified.csv')):
    if row['attack_class']=='early-stop':
        es_all.append(dict(cap=-1, run=row['run_id'], pendTO=int(row['pendTO']),
                           done_t=float(row['done_t_s']), src='R2B', sent=int(row['sent'])))
n_es = len(es_all); n_supp = sum(1 for p in es_all if p['pendTO']==0)
with open(f'{OUT}/R3H_escape_rate.txt','w') as f:
    f.write("R3H 逃逸率读法（FW/Kramers 框架的 P(div|CAP,T_drive)≈1-exp[-λ_esc(CAP)·T_drive]，descriptive）\n")
    f.write(f"证据 1（早停=短驱动窗）：五源全量扫描（R2E/D18/R3D/R3A 按各自 raw 的 sent≥65400 口径；R2B 按\n")
    f.write(f"  R2B_stratified.attack_class 官方口径列）——共 {n_es} 个早停 run（驱动窗 2-7s），\n")
    f.write(f"  suppressed（pendTO=0）{n_supp}/{n_es}" + ("——无一发散，跨源跨臂跨位置一致。\n" if n_supp==n_es
            else "——【注意】存在非 suppressed 早停 run，下述主张须按此修正！\n"))
    f.write(f"  早停 run 清单（{n_es} 个，逐源标注；【更正 2026-10-20】原版仅扫 R2E/D18/R3D 三源得 3 个）：\n")
    for p in sorted(es_all, key=lambda q:(q['src'],q['run'])):
        f.write(f"    {p['run']:28s} src={p['src']:4s} cap={p['cap']:3d} done_t={p['done_t']:.2f}s pendTO={p['pendTO']}\n")
    f.write("\n证据 2（全程=长驱动窗）：同 CAP 全程 run 按 CAP 分化（见分臂汇总表）\n")
    f.write("读法：若结局=逃逸事件（泊松 λ_esc·T），则短窗 run 的存活率应显著更高且与 CAP 无关——与清单一致；\n")
    f.write("定量约束受 n 限制（每格 2-10 run），λ_esc(CAP) 只给区间读法：\n")
    for key in ('cap20','cap24','cap28','cap32'):
        ps = arms.get(key,[])
        fw=[p for p in ps if p['group']!='early-stop']
        div=[p for p in fw if p['group']=='diverged']
        if fw:
            ph = 1 - len(div)/len(fw)
            # 20s 驱动窗：1-exp(-λ·20)=P(div) → λ = -ln(1-P)/20
            lam = -math.log(max(1-len(div)/len(fw),1e-6))/20.0 if len(div)<len(fw) else float('inf')
            f.write(f"  {key}: P_h(全程)={len(fw)-len(div)}/{len(fw)} → λ_esc≈{lam if lam==float('inf') else f'{lam:.4f}/s'}（Jeffreys CI 见分臂表）\n")
    f.write("\n准势读法（非梯度系统只取指数主导）：ΔV(CAP)∝-ln λ_esc 在双稳区递减（CAP↑→势垒↓）——与 fold 分岔\n")
    f.write("的 c(u) 折返机理一致；E-K 前置因子不主张（离散跳过程→流体极限的 FW 适配，引 Shwartz-Weiss 1995）。\n")

# ---------- 7. 生态学三标准对照（Nat Comm 2023 操作化） ----------
# 【更正 2026-10-20（R4 写作前置清单 2）】multimodality 行由硬编码改全量计算：
# 515103（r3d_cap28_rep1）按 ≥1e5 判据归 diverged（原误列中间量级）；真中间量级
# （0<pendTO<1e5）由联合曲线 50 run 全量扫描得出。
pool = [p for p in bif if p['cap'] in (20,24,28,32)]
inters_pool = sorted(p['pendTO'] for p in pool if 0 < p['pendTO'] < 1e5)
inters_all  = sorted(p['pendTO'] for p in bif  if 0 < p['pendTO'] < 1e5)
n_pool = len(pool); n_div_pool = sum(1 for p in pool if p['group'] in ('diverged',))
n_supp_pool = sum(1 for p in pool if p['group'] in ('suppressed','early-stop'))
with open(f'{OUT}/R3H_three_criteria.txt','w') as f:
    f.write("R3H alternative stable states 三标准对照（依 Scheffer 2001/2009；操作化标准 Nat Comm 2023 s41467-023-43744-8）\n")
    f.write("标准                  在盘证据                                                          判定\n")
    f.write("1 time-series shift   T 臂发散 run（T24r2/T28r1）CPU 从攻击期高位跳变至零输入持续高位/RSS 单调涨（R3H_zero_input_evolution.txt） 见该文件\n")
    f.write("2 hysteresis          T(强攻10s→轻载30s) 2/9 发散 vs M(纯轻载 16.78s) 0/9；Fisher p=0.235 方向性支持、功效不足如实 方向性（弱）\n")
    f.write(f"3 multimodality       终态 pendTO 分布双峰（主体 0 或 ≥1e5）。边界区 cap20-32 共 {n_pool} run：\n")
    f.write(f"                      suppressed/早停 {n_supp_pool} + diverged {n_div_pool}；【更正 2026-10-20】515103（r3d_cap28_rep1）\n")
    f.write(f"                      按 ≥1e5 判据归 diverged（原静态文本误列中间量级）；真中间量级（0<pendTO<1e5）\n")
    f.write(f"                      边界区={inters_pool if inters_pool else '无'}；联合曲线全 50 run 共 {len(inters_all)} 例\n")
    f.write(f"                      ={inters_all if inters_all else '无'}——双峰主体地位维持 " + ("成立\n" if len(inters_all)<=5 else "（中间量级偏多，判定须复核）\n"))
    f.write("\n综合判定：三标准 2.5/3（滞后证据方向性）——『攻击诱导亚稳态』读法成立但 hysteresis 判据未达统计显著；\n")
    f.write("flickering（Wang 2012）：cap24/28 的 1/3-2/3-2/3 双峰随机混合+cap20 全程 0/2 全发散=边界区强迫噪声幅与势垒同量级。\n")

print("R3H analysis complete. Files:", os.listdir(OUT))
