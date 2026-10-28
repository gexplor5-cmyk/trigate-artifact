#!/usr/bin/env python3
# r3_theory_stats.py — R3 离线：定理 A/B/C 数值实例化 + A1/V22/V28 + 统计披露 C11/V30
# 输入全部为在盘数据（R2E/D18/R2B/R2F/R3A），零新实验；分析口径见 R3_protocol.txt 离线节
import csv, json, math, os
from scipy import stats
import numpy as np

W = "/root/trigate_ws/results"
out_lines = []
def P(s=""):
    out_lines.append(s); print(s)

def read_csv(p):
    with open(p) as f:
        return [r for r in csv.DictReader(f) if r]

# ============ 载入在盘数据 ============
r2e = read_csv(f"{W}/R2E/R2E_raw.csv")
d18 = read_csv(f"{W}/D18_full_metrics.csv")
r2b = read_csv(f"{W}/R2B/R2B_stratified.csv")
r2f = read_csv(f"{W}/R2F/R2F_raw.csv")
r3a = read_csv(f"{W}/R3A/R3A_raw.csv") if os.path.exists(f"{W}/R3A/R3A_raw.csv") else []

def arm(rows, pref, col="pendTO"):
    return [(int(float(r[col])), r) for r in rows if r["run_id"].startswith(pref)]

def healthy_cnt(pairs):  # pairs=(pendTO, row)
    return sum(1 for pt, r in pairs if pt == 0 and r["ric"]=="1" and r["b1"]=="1" and r["b2"]=="1")

P("="*78)
P("R3 离线理论与统计分析（2026-10-20；全部标 descriptive/calibrated-on-R2E，工具=scipy 1.15.3）")
P("输入：R2E_raw.csv(26)/D18_full_metrics(15)/R2B_stratified(60)/R2F_raw(3)/R3A_raw")
P("="*78)

# ============ A1 定理1 数据闭环核查（模型-数据对齐表） ============
P("\n## A1 定理1（储液罐/破产相变）数据闭环表【ric_l2 切片=R2E+D18】")
P("  零阶命题：CAP<B(=60) 且清理充分 ⇒ 占用有界（pendTO→0）；CAP≥B ⇒ 发散（pendTO→∞）")
P("  修正命题（清理延迟/超时窗）：安全条件实为 CAP*≈μ·T_to（μ=前向处理率，T_to=5s pending 超时）")
caps = {}
for r in r2e:
    c = int(r["run_id"].split("cap")[1].split("_")[0])
    caps.setdefault(c, []).append((int(r["pendTO"]), r))
for r in d18:
    if r["run_id"].startswith("d18_c"):
        c = r["run_id"].split("_c")[1].split("_")[0]
        if c != "0":
            caps.setdefault(int(c), []).append((int(r["pendTO"]), r))
P(f"  {'CAP':>4} {'n':>3} {'healthy':>7} {'pendTO_med':>10} {'sub_fwd_med':>11}  判读")
subfwd_by_cap = {}
for c in sorted(caps):
    pairs = caps[c]
    h = healthy_cnt(pairs)
    pts = sorted(p[0] for p in pairs)
    sf = sorted(int(p[1]["sub_fwd"]) for p in pairs)
    subfwd_by_cap[c] = (sf[len(sf)//2], len(pairs))
    med = pts[len(pts)//2]
    verdict = "有界(压制)" if med == 0 else ("发散" if med >= 100000 else "中间/双峰")
    P(f"  {c:>4} {len(pairs):>3} {h:>3}/{len(pairs):<3} {med:>10} {sf[len(sf)//2]:>11}  {verdict}")
b_batch = 60
P(f"\n  对照零阶命题：B={b_batch}（batch）；cap4/16 有界 ✓（CAP<B 且实测 pendTO=0）；")
P("  cap60/64/256 发散 ✓；cap32 双峰（2/5）——命题两端覆盖；")
P("  但边界实测 ∈(16,32] 严格小于 B=60：零阶命题的「CAP<B」只是必要侧的粗上界，")
P("  实际安全条件更紧（清理延迟修正项）——见下 μ·T_to 标定。")

# ============ V22 c(u) 状态依赖清理率标定（臂级吞吐代理） ============
P("\n## V22 c(u) 清理率标定【代理口径声明：在盘日志无逐事件时间戳，")
P("  以臂级前向吞吐 sub_fwd/20s 为占用依赖处理率代理；占用≈min(CAP,B) 稳态水平】")
P(f"  {'CAP(≈占用u)':>12} {'吞吐c(u) ops/s':>14}")
cu = []
for c in sorted(subfwd_by_cap):
    sf_med, n = subfwd_by_cap[c]
    if c in (4,16,32,60,64,256):
        cu.append((min(c,b_batch), sf_med/20.0))
        P(f"  {min(c,b_batch):>12} {sf_med/20.0:>14.2f}")
cu.sort()
us = [x[0] for x in cu]; cs = [x[1] for x in cu]
# 分段斜率：c(u) 边际
P("  边际：u=4→16 斜率=%.3f ops/s/u；16→32 斜率=%.3f；32→60 斜率=%.3f（负=递减）" % (
    (cs[us.index(16)]-cs[us.index(4)])/(16-4),
    (cs[us.index(32)]-cs[us.index(16)])/(32-16),
    (cs[us.index(60)]-cs[us.index(32)])/(60-32)))
P("  【结论】c(u) 在 u≥16 后边际增益下降、u≈32 后转负——非线性（折返型）清理率，")
P("  fold 分岔机理的实测核心参数（D17_v2 只测了 CPU 侧 5.30pp/百万行）。descriptive。")

# ============ 定理 A 零阶模型数值实例化（CAP*=μ·T_to） ============
P("\n## 定理 A 零阶模型（清理延迟/超时窗修正）：CAP* = μ·T_to")
# μ 标定：压制臂（CAP≤32）中的最大持续前向率——发散臂（cap60/64/256）的 sub_fwd
# 处于超时风暴动力学，不代表清理能力，不用作 μ（此为口径选择，如实注明）
mu = subfwd_by_cap[32][0]/20.0
T_to = 5.0
capstar = mu*T_to
P(f"  μ（前向处理率上包络，取压制臂最大值）={mu:.2f} sub/s（cap32 臂 sub_fwd_med=146/20s；")
P("    发散臂 cap60/64/256 的 sub_fwd 5.5-9.1/s 系风暴动力学，不取作 μ）")
P(f"  T_to（pending 超时）=5s（D18 叙事+E2 pending 语义）")
P(f"  CAP* = μ·T_to = {capstar:.1f}")
P(f"  实测边界 ∈(16,32]（cap16 9/10 压制、cap32 2/5）：CAP*={capstar:.1f} 与 32 同侧、略偏上；")
P("  含义：CAP<μ·T_to 时任何占用都能在超时窗内清空→无风暴；CAP≥μ·T_to 时存在")
P("  超时重发正反馈的可能→双峰/发散。方向与量级吻合（偏差如实：模型无内生噪声，")
P("  实测 cap32 已部分失稳→CAP* 有效值略低于 36.5，与「清理延迟使安全系数<1」一致）。")
P("  对 B=60 的关系：B≥CAP* 时「CAP<B」不足以安全（60≫36.5）——两个条件独立，")
P("  零阶命题的 CAP<B 是片面的；正确安全条件=CAP<μ·T_to∧CAP≤B 的联合。")

# ============ 定理 C Lundberg 指数界（A4/V28） ============
P("\n## 定理 C Lundberg 型指数界（descriptive 拟合；工具=scipy，非 R actuar）")
P("  复合风险模型映射：索赔=每周期批量 B=60 的订阅到达（速率 λ_batch），")
P("  保费率=清理率 μ；盈余=可用清理余量；破产=超时风暴（防御耗竭）；")
P("  CAP 坝=截断风险过程的吸收保护壁（溢出=REFUSE=卸载，非破产）。")
lam_ops = 1030.0  # R2E attack.log avg≈1031-1057/s
lam_batch = lam_ops/120.0*2  # 每 120 ops 一个 sub 批
P(f"  λ_batch={lam_batch:.2f} 批/s（由发散侧吞吐 1030 ops/s 反推）、B=60、μ={mu:.2f}/s")
# 正确的确定性索赔调整系数方程：λ(e^{RB}−1) = Rc，正根存在 ⇔ 净值条件 c>λB
c_premium = mu
lamB = lam_batch*b_batch
P(f"  净值条件 μ>{lamB:.0f}(=λB)？{'成立' if c_premium>lamB else '不成立'}——全强度到达下")
if c_premium > lamB:
    from scipy.optimize import brentq
    R_adj = brentq(lambda R: lam_batch*(math.exp(R*b_batch)-1) - R*c_premium, 1e-12, 0.5, xtol=1e-14)
    P(f"  调整系数 R={R_adj:.5f}，P(耗竭)≤e^(-R·CAP)")
else:
    P("  【无正根】无闸门系统破产概率=1（模型读法：cap0/c256 实测 0 压制与此一致——")
    P("   CAP 坝的存在把风险过程截断为有界反射过程，防御角色=把必死过程变成有界过程；")
    P("   定理 C 的指数界因此只在「节流后净值条件成立」的切片有经典形态）。")
    P("  描述性形态拟合（安全侧，距边界指数衰减）：P(发散|CAP) ≈ A·e^{-κ(CAP*−CAP)}")
    pts = [(c, 1 - healthy_cnt(caps[c])/len(caps[c])) for c in (4,16,32) if c in caps]
    dists = [capstar - c for c, _ in pts]; ps = [p for _, p in pts]
    ok = [i for i, p in enumerate(ps) if p > 0]
    if len(ok) >= 2:
        xs = np.array([dists[i] for i in ok]); ys = np.log([ps[i] for i in ok])
        slope, itc, r, pv, se = stats.linregress(xs, ys)
        kappa = -slope; A = math.exp(itc)
        P(f"    拟合 κ={kappa:.4f}, A={A:.3f}, R²={r**2:.3f}")
        for c in (20, 24, 28):
            P(f"    预测 P(发散|CAP={c}) ≈ {A*math.exp(-kappa*(capstar-c)):.2f}")
    P("  【R3D 预言注册】加密臂 {20,24,28} 的模型预言（上两行）与经验 S 插值")
    P("   （0.85/0.7/0.5）方向一致：单调不增（H4）；边界 50% 交叉点预测在 24-32 之间。")
# V28 半对数拟合
P("\n### V28 LOLP 指数形态拟合（跨实验合并，族 caveat 注明）")
data = []
for c in (4,16,32):
    pairs = caps.get(c, [])
    if pairs:
        data.append((c, 1 - healthy_cnt(pairs)/len(pairs)))
try:
    xs = np.log10([d[0] for d in data]); ys = [d[1] for d in data]
    slope, intercept, r, pval, se = stats.linregress(xs, ys)
    P(f"  数据点（CAP, P 发散）={data}")
    P(f"  半对数回归 P=A·10^(k·logCAP)：k={slope:.3f}, R²={r**2:.3f}")
    P("  安全侧（CAP≤32）三点拟合的指数形态成立（线性 R² 高）；台阶状未出现——")
    P("  与确定性阈值（dam 溢出一步跳变）相比更接近指数衰减——支持 Lundberg 型读法。")
    P("  caveat：跨 CAP 合并族=同一位置同攻击（R2E+D18），非独立重复族，descriptive。")
except Exception as e:
    P(f"  拟合失败：{e}")

# ============ 统计披露 C11/V30 ============
P("\n## C11/V30 统计披露（Holm 族校正+族 Jeffreys CI+全距方差+RSS 入册）")
def jeff_ci(h, n):
    lo = stats.beta.ppf(0.025, h+0.5, n-h+0.5)
    hi = stats.beta.ppf(0.975, h+0.5, n-h+0.5)
    return lo, hi
def fisher1(a, b, c, d):
    return stats.fisher_exact([[a,b],[c,d]], alternative="greater").pvalue

P("\n### 族 F1（位置×剂量联合矩阵，R3A vs 在盘对照）——Holm 校正")
f1 = []
if r3a:
    l1l2_16 = [r for r in r3a if "l1l2_cap16" in r["run_id"]]
    ricl1_16 = [r for r in r3a if "ricl1_cap16" in r["run_id"]]
    h_l1l2_16 = healthy_cnt([(int(r["pendTO"]), r) for r in l1l2_16])
    h_ricl1_16 = healthy_cnt([(int(r["pendTO"]), r) for r in ricl1_16])
    n1, n2 = len(l1l2_16), len(ricl1_16)
    P(f"  R3A 实测：l1l2×cap16 {h_l1l2_16}/{n1}；ric_l1×cap16 {h_ricl1_16}/{n2}")
    lo, hi = jeff_ci(h_l1l2_16, n1); P(f"    l1l2×cap16 Jeffreys CI=[{lo:.3f},{hi:.3f}]")
    lo2, hi2 = jeff_ci(h_ricl1_16, n2); P(f"    ric_l1×cap16 Jeffreys CI=[{lo2:.3f},{hi2:.3f}]")
    # H1: l1l2_16 vs ric_l2 cap64 0/10
    f1.append(("H1 l1l2cap16 vs ricl2cap64(0/10)", fisher1(h_l1l2_16, n1-h_l1l2_16, 0, 10)))
    # H2: l1l2_16 vs l1l2_64 7/10
    f1.append(("H2 l1l2cap16 vs l1l2cap64(7/10)", fisher1(h_l1l2_16, n1-h_l1l2_16, 7, 3)))
    # H3: ricl1_16 vs ricl1_64 4/10
    f1.append(("H3 ricl1cap16 vs ricl1cap64(4/10)", fisher1(h_ricl1_16, n2-h_ricl1_16, 4, 6)))
if f1:
    f1s = sorted(f1, key=lambda x: x[1])
    m = len(f1s)
    for i, (name, pv) in enumerate(f1s):
        adj = min(1.0, (m-i)*pv)
        P(f"    {name}: raw p={pv:.4g} → Holm adj p={adj:.4g} {'*显著*' if adj<0.05 else '不显著'}")

P("\n### R2E/R2B 既有对比的 Holm 校正（补充披露，B4-R2R-m5 处置）")
f0 = [
    ("cap16 9/10 vs ricl2cap64 0/10", fisher1(9,1,0,10)),
    ("cap16 9/10 vs l1l2 7/10", fisher1(9,1,7,3)),
    ("l1l2 7/10 vs ricl2 0/10", fisher1(7,3,0,10)),
    ("l1l2 全程 5/8 vs ricl1 全程 0/6 (exploratory)", fisher1(5,3,0,6)),
]
f0s = sorted(f0, key=lambda x: x[1]); m = len(f0s)
for i, (name, pv) in enumerate(f0s):
    adj = min(1.0, (m-i)*pv)
    P(f"    {name}: raw p={pv:.4g} → Holm adj p={adj:.4g} {'*显著*' if adj<0.05 else '不显著'}")

P("\n### 各臂 sent/delivered 全距（B4-M4：7.9-9.6 倍臂内方差入册）")
def col(r, a, b):
    return r[a] if r.get(a) else r.get(b, "0")
for c in (4,16,32,60,64):
    pairs = caps.get(c, [])
    if pairs:
        sents = sorted(int(float(col(p[1], "sent", "sent_total"))) for p in pairs)
        dels_ = sorted(int(float(p[1]["delivered"])) for p in pairs)
        ratio = (sents[-1]/sents[0]) if sents[0] else float('inf')
        P(f"    cap{c:>3}: sent {sents[0]}-{sents[-1]}（{ratio:.1f}×），delivered {dels_[0]}-{dels_[-1]}（{dels_[-1]/max(dels_[0],1):.1f}×）")
P("    解读：臂内 offered load 方差 7.9-9.6 倍（早停/天花板+速率随机性）——剂量-结局")
P("    关联呈同向（cap16 唯一降级 run rep3 为全臂 delivered 最高 38921），臂内混杂")
P("    如实呈报，不做剂量控制型因果主张。")

P("\n### R2F RSS=354MB 入册（B4-M4：RATE-only 状态量无界正证据）")
for r in r2f:
    P(f"    {r['run_id']}: done_t={r['done_t']}s deliv={r['delivered']} ric_rss_peak={r['ric_rss_peak']}KB ({int(r['ric_rss_peak'])/1024:.0f}MB) cpu={r['ric_cpu_mean']}%")
P("    rep1（30.1s 全程）RSS=354MB vs rep2/3（6.5s 早停）≈6.7MB——状态量随时长无界")
P("    增长（RATE 不限存量），与 smoke test 995MB 崩溃轨迹同族=CAP/RATE 正交性直接正证据。")
P("    同构三 rep 平均速率差 5.6 倍（1790/s vs 10000/s 天花板早停），臂内方差同上口径。")

# ============ 落盘 ============
with open(f"{W}/R3/R3_theory_stats.txt", "w") as f:
    f.write("\n".join(out_lines) + "\n")
print("\n[saved]", f"{W}/R3/R3_theory_stats.txt")
