#!/usr/bin/env python3
# R3H 扩展分析（R4 写作前置清单 4+5：定向创新方案 2 完整版+方案 1 实例化，2026-10-20）
# 输入：R3D 27 run monitor.csv（10Hz）+R3D_raw 结局+R2E/D18/R3A/R3D 联合曲线（r3h_analysis 同源）
# 输出：results/R3H/R3H_potential_landscape.txt（势景观+M2+bootstrap）/R3H_deltav_table.txt（ε 反演+ΔV 预言表）/R3H_hysteresis.txt（分岔滞后环）
# 全部 descriptive；非梯度系统只报准势读法；M2 因 10Hz 欠采样报下界读法（不主张绝对值）
import csv, math, os
import numpy as np

W = '/root/trigate_ws'
OUT = f'{W}/results/R3H'
rng = np.random.default_rng(20261020)

runs = {row['run_id']: row for row in csv.DictReader(open(f'{W}/results/R3D/R3D_raw.csv'))}

def load_mon(rid):
    t=[];cpu=[]
    for r in csv.reader(open(f'{W}/results/R3D/{rid}/monitor.csv')):
        if not r or r[0]=='t': continue
        try: t.append(float(r[0])); cpu.append(float(r[1]))
        except (ValueError, IndexError): pass
    return np.array(t), np.array(cpu)

M = {rid: load_mon(rid) for rid in runs}

def outcome(row):
    pt=int(row['pendTO'])
    return 'diverged' if pt>=1e5 else ('suppressed' if pt==0 else 'intermediate')
grp={rid:outcome(r) for rid,r in runs.items()}

# ---------- A. KM：M1+M2 联合估计（run 级 block bootstrap CI） ----------
def pairs(rid, t0, dt=1.0):
    t,cpu=M[rid]; X=[];D=[]
    for i in range(len(t)-1):
        if t[i]<t0: continue
        j=np.searchsorted(t,t[i]+dt)
        if j>=len(t) or abs(t[j]-t[i]-dt)>0.3: continue
        X.append(cpu[i]); D.append(cpu[j]-cpu[i])
    return np.array(X),np.array(D)

def km(X,D,grid,bw,mo=1):
    wgt=np.exp(-0.5*((X-grid)/bw)**2); s=wgt.sum()
    if s<1e-9: return np.nan
    v=(wgt*D).sum()/s if mo==1 else (wgt*D**2).sum()/s/dt_ref
    return v

grid=np.arange(0,105,2.5); bw=10.0; dt_ref=1.0

def pool_boot(rids, t0, B=200):
    """run 级 block bootstrap：重采样 run（保 run 内轨迹完整），返回 M1/M2 均值曲线与 95% 带"""
    trajs=[pairs(r,t0) for r in rids]; trajs=[(x,d) for x,d in trajs if len(x)>5]
    if not trajs: return None,None,None,None,None
    def curve(trs):
        X=np.concatenate([t[0] for t in trs]); D=np.concatenate([t[1] for t in trs])
        m1=np.array([km(X,D,g,bw,1) for g in grid])
        m2=np.array([km(X,D,g,bw,2) for g in grid])
        return m1,m2
    m1,m2=curve(trajs)
    bs1=[];bs2=[]
    n=len(trajs)
    for _ in range(B):
        sel=[trajs[rng.integers(n)] for _ in range(n)]
        a,b=curve(sel); bs1.append(a); bs2.append(b)
    bs1=np.array(bs1);bs2=np.array(bs2)
    q1=np.nanpercentile(bs1,[2.5,97.5],axis=0); q2=np.nanpercentile(bs2,[2.5,97.5],axis=0)
    return m1,q1,m2,q2,len(trajs)

# ---------- B. 势景观（准势：U(x) = -∫ M1(x) dx，仅漂移主导项，非梯度系统声明） ----------
def potential(m1):
    u=np.zeros_like(m1)
    for i in range(1,len(m1)):
        if np.isnan(m1[i]) or np.isnan(m1[i-1]): u[i]=u[i-1]; continue
        u[i]=u[i-1]-0.5*(m1[i]+m1[i-1])*(grid[i]-grid[i-1])
    return u

def fixed_points(m1):
    zs=[]
    for i in range(1,len(m1)-1):
        if np.isnan(m1[i-1]) or np.isnan(m1[i+1]): continue
        if m1[i-1]*m1[i+1]<0: zs.append(grid[i])
    return zs

sup_pool=[r for r in runs if grp[r]=='suppressed' and (r.startswith('r3d_cap') or r.startswith('r3d_hys_M'))]
div_pool=[r for r in runs if grp[r]=='diverged']
att_pool=[r for r in runs if r.startswith('r3d_cap') or r.startswith('r3d_hys_T')]

m1s,q1s,_,_,ns=pool_boot(sup_pool,18.0); m1d,q1d,_,_,nd=pool_boot(div_pool,18.0)
m2s_q=None
_,_,m2a,q2a,na_=pool_boot(att_pool,18.0)

with open(f'{OUT}/R3H_potential_landscape.txt','w') as f:
    f.write("R3H 势景观与 KM 完整版（R4 写作前置清单 4：方案 2 落地，descriptive）\n")
    f.write("口径：状态 X=RIC CPU%（10Hz）；攻击窗 t0=18s、Δ=1s；NW bw=10；run 级 block bootstrap B=200（95% 带）\n")
    f.write("诚实声明：①非梯度系统——U(x)=-∫M1dx 仅为准势读法（漂移主导项），不做势函数唯一性主张；\n")
    f.write("②M2=每秒条件方差（E[(ΔX)^2|X]/Δt）——10Hz 对消息级跳变欠采样→M2 为**下界读法**，不主张绝对值；\n")
    f.write("③bootstrap 重采样单元=run（保 run 内轨迹相关结构），CI 反映 run 间变异。\n\n")
    f.write(f"== 压制侧漂移场（suppressed+M 臂 n={ns}）与发散侧（diverged n={nd}）==\n")
    f.write("CPU%:  " + " ".join(f"{g:>6.0f}" for g in grid if int(g)%10==0) + "\n")
    for name,m1,q in (("M1_sup",m1s,q1s),("M1_div",m1d,q1d)):
        sel=[i for i,g in enumerate(grid) if int(g)%10==0]
        f.write(f"{name}: " + " ".join(f"{m1[i]:+.2f}" for i in sel) + "\n")
        f.write(f"  95%带下: " + " ".join(f"{q[0][i]:+.2f}" for i in sel) + "\n")
        f.write(f"  95%带上: " + " ".join(f"{q[1][i]:+.2f}" for i in sel) + "\n")
    f.write("\n== M2 扩散项（下界读法，攻击池 n=%d）==\n" % na_)
    sel=[i for i,g in enumerate(grid) if int(g)%10==0]
    f.write("M2(x): " + " ".join(f"{m2a[i]:6.1f}" if not math.isnan(m2a[i]) else "   nan" for i in sel) + "\n")
    f.write("M2 下界带: [" + " ".join(f"{q2a[0][i]:5.1f}" if not math.isnan(q2a[0][i]) else "  nan" for i in sel) + "]\n")
    f.write("        [" + " ".join(f"{q2a[1][i]:5.1f}" if not math.isnan(q2a[1][i]) else "  nan" for i in sel) + "]\n\n")
    f.write("== 准势 U(x)（-∫M1 dx，任意单位；两个结局池分别重建）==\n")
    us=potential(m1s); ud=potential(m1d)
    f.write("U_sup: " + " ".join(f"{u:+7.1f}" for i,u in zip(range(len(grid)),us) if int(grid[i])%10==0) + "\n")
    f.write("U_div: " + " ".join(f"{u:+7.1f}" for i,u in zip(range(len(grid)),ud) if int(grid[i])%10==0) + "\n")
    f.write(f"\n不动点（M1 符号翻转，bootstrap CI 见下）：sup 池 {fixed_points(m1s)}｜div 池 {fixed_points(m1d)}\n")
    # 不动点 bootstrap CI
    def fp_boot(rids,B=200):
        trajs=[pairs(r,18.0) for r in rids]; trajs=[(x,d) for x,d in trajs if len(x)>5]
        if not trajs: return []
        res=[]
        for _ in range(B):
            sel=[trajs[rng.integers(len(trajs))] for _ in range(len(trajs))]
            X=np.concatenate([t[0] for t in sel]); D=np.concatenate([t[1] for t in sel])
            m=np.array([km(X,D,g,bw,1) for g in grid]); res.append(fixed_points(m))
        flat=[z for r in res for z in r]
        return (np.percentile(flat,[2.5,97.5]) if flat else (float('nan'),float('nan')))
    ci_s=fp_boot(sup_pool); ci_d=fp_boot(div_pool)
    f.write(f"不动点 bootstrap 95%CI：sup 池 {ci_s[0]:.1f}-{ci_s[1]:.1f}｜div 池 {ci_d[0]:.1f}-{ci_d[1]:.1f}\n")

# ---------- C. 分岔图+滞后环（M 支=轻载上行 forcing 低；T 支=强攻后回落 forcing 高） ----------
with open(f'{OUT}/R3H_hysteresis.txt','w') as f:
    f.write("R3H 分岔图滞后环（R4 清单 4：CAP 扫描×双 forcing 支，descriptive）\n")
    f.write("M 支=hys_M（纯轻载 16.78s 名义驱动，低 forcing）；T 支=hys_T（强攻 10s→轻载，高 forcing 后回落）\n")
    f.write("结局=终态 pendTO≥1e5 发散。同一 CAP 下两支结局分布差异=滞后环的实测侧写。\n")
    f.write("CAP   M支 div/total   T支 div/total   支间差\n")
    for cap in (24,28,32):
        M_r=[f'r3d_hys_M_cap{cap}_rep{k}' for k in (1,2,3) if f'r3d_hys_M_cap{cap}_rep{k}' in runs]
        T_r=[f'r3d_hys_T_cap{cap}_rep{k}' for k in (1,2,3) if f'r3d_hys_T_cap{cap}_rep{k}' in runs]
        dM=sum(1 for r in M_r if grp[r]=='diverged'); dT=sum(1 for r in T_r if grp[r]=='diverged')
        f.write(f"{cap:3d}   {dM}/{len(M_r)}           {dT}/{len(T_r)}         "
                f"{'T>M（滞后方向）' if dT>dM else ('无差异' if dT==dM else '反向（如实）')}\n")
    f.write("\n解读（n=3/支，功效注记）：T 2/9 vs M 0/9 的支间差（Fisher p=0.235）为方向性滞后证据——\n")
    f.write("同一参数（CAP）下，历史 forcing 决定终态所在吸引盆=路径依赖；统计显著性未达（如实），\n")
    f.write("与 three_criteria 的 hysteresis 方向性（弱）判定一致。\n")

# ---------- D. ε 反演+ΔV 预言表（R4 清单 5：方案 1 实例化） ----------
def eps_from_drift(rids):
    """ε = -dM1/dx 在压制池稳定不动点处的局部斜率（OU 线性化）；bootstrap CI"""
    trajs=[pairs(r,18.0) for r in rids]; trajs=[(x,d) for x,d in trajs if len(x)>5]
    X=np.concatenate([t[0] for t in trajs]); D=np.concatenate([t[1] for t in trajs])
    m=np.array([km(X,D,g,bw,1) for g in grid])
    fps=fixed_points(m)
    if not fps:
        # 兜底：无符号翻转（区间内单侧）时取 |M1| 最小格点为拟不动点（方向性读法，如实标注）
        i0=int(np.nanargmin(np.abs(m))); x0=grid[i0]
        i1,i2=max(i0-2,0),min(i0+3,len(grid))
        slope=np.polyfit(grid[i1:i2],m[i1:i2],1)[0]
        return -slope, x0, '无符号翻转（|M1| 最小格点兜底）'
    x0=fps[0]; i0=int(np.argmin(abs(grid-x0)))
    i1,i2=max(i0-2,0),min(i0+3,len(grid))
    slope=np.polyfit(grid[i1:i2],m[i1:i2],1)[0]
    return -slope, x0, fps

# 稳态方差交叉核对（OU: σ²=D/(2ε)，D 取 M2 下界 → ε 下界= D/(2σ²)）
def steady_var(rids, t0=25.0):
    vs=[]
    for r in rids:
        t,cpu=M[r]; m=(t>=t0)
        if m.sum()>=20: vs.append(float(np.var(cpu[m],ddof=1)))
    return float(np.mean(vs)) if vs else float('nan'), len(vs)

lam = {'cap20':(2,2),'cap24':(1,3),'cap28':(1,3),'cap32':(3,5)}  # (div, n) 全程口径
eps,x0,fps=eps_from_drift(sup_pool)
sig2,nsv=steady_var([r for r in sup_pool if r.startswith('r3d_hys_M') or True])
with open(f'{OUT}/R3H_deltav_table.txt','w') as f:
    f.write("R3H ε 反演与 ΔV 预言表（R4 清单 5：方案 1 实例化，descriptive）\n")
    f.write("ε 反演（OU 线性化：M1(x)≈-ε(x-x*)）：ε = -dM1/dx @ 稳定不动点\n")
    f.write(f"  压制池稳定不动点 x*={x0:.1f}%（池内不动点集 {fps}）；ε_drift={eps:.3f} /s\n")
    f.write(f"  交叉核对（下界读法）：压制池稳态方差 σ²={sig2:.2f}（n={nsv} run，t≥25s 窗）——\n")
    f.write("  OU 关系 ε=D/(2σ²) 需 D=M2 绝对值，而 M2 系 10Hz 下界→该交叉核对只能给 ε 上界/下界\n")
    f.write("  约束（欠定，如实注明，不给出点值）。\n\n")
    f.write("ΔV 预言表（Kramers 读法：λ_esc = A·exp(-ΔV)，前置因子 A 不主张——报相对势垒 ΔV_rel=-ln λ_esc）\n")
    f.write("CAP   P_div(全程)   λ_esc(/s)      ΔV_rel=-ln λ   Jeffreys95(λ 由 P_div CI 反解)\n")
    from scipy.stats import beta as B
    for key,(k,n) in lam.items():
        P=k/n
        if P>=1: lamv=float('inf'); dv=float('inf')
        else: lamv=-math.log(1-P)/20.0; dv=-math.log(lamv) if lamv>0 else float('inf')
        lo=B.ppf(0.025,k+0.5,n-k+0.5); hi=B.ppf(0.975,k+0.5,n-k+0.5)
        lam_lo=-math.log(max(1-hi,1e-6))/20.0 if hi<1 else float('inf')
        lam_hi=-math.log(max(1-lo,1e-6))/20.0
        def fmt(x): return "inf" if math.isinf(x) else f"{x:.4f}"
        f.write(f"{key[3:]:>3s}   {k}/{n}={P:.2f}      {fmt(lamv):>8s}      "
                f"{'inf' if math.isinf(dv) else f'{dv:.3f}':>8s}      [{fmt(lam_lo)}, {fmt(lam_hi)}]\n")
    f.write("\n读法（可检验预言，非拟合回顾）：\n")
    f.write("  1) ΔV_rel 随 CAP 单调下降（cap24/28→cap32）=势垒随闸门放宽降低——fold 分岔侧写；\n")
    f.write("  2) cap20 P=1.0（0/2 全发散，n=2 功效注记）给 λ→inf/ΔV→-inf 的边界读法（不外推）；\n")
    f.write("  3) E-K 一维显式公式（双井分段线性）可对读形态（不引前置因子数值主张）；\n")
    f.write("  4) 跳过程→流体极限适配：Shwartz-Weiss 1995（大偏差通道）；Salamati-Alvaro 2025 为\n")
    f.write("     离散 CTMC+escape probability 最近邻（非 O-RAN、无安全视角、无 10Hz 轨迹重建）。\n")
    f.write("  5) P-A 驱动窗预言的直接检验（CAP=24×T_drive 扫描）未做——本表为区间的可检验化，\n")
    f.write("     非回顾拟合（诚实边界，见主汇总 P-A）。\n")
print("extension complete:", os.listdir(OUT))
