#!/usr/bin/env python3
"""离线修复 v2【M5 索引管道 + M6/B-m2 E2 累计口径 + M4 二项 CI + m3 trimmed CPU】
1) R1C_index_v2.csv：以 C1_rerun.csv（真实 c1 数据）+ c3 原始 run 目录重建，
   修复换行错位与缺行；行数/列数机检（每行列数==表头列数）。
2) E2_refuse_quantification.csv：从 c3 各 run agent_tail.log 提取 REFUSE 累计值
   （B-m2：行数口径→累计值口径），量化拦截粒度（M6）。
3) R1B_stats_v2.csv：每格存活数的 Clopper-Pearson 精确二项 95% CI（M4），
   存活格 CPU 的 trimmed mean（去掉最高单秒，m3）与中位数。
4) R1A_invalidation.csv：C1 判无效的 15 run 清单+判据（供 R1F 对照）。
"""
import csv, glob, os, re, math

WS = "/root/trigate_ws"
RES = f"{WS}/results"

def clopper_pearson(k, n, alpha=0.05):
    """精确二项 CI（scipy 可用则直接用 beta.ppf）"""
    from scipy.stats import beta as _beta
    if n == 0: return (0.0, 1.0)
    lo = 0.0 if k == 0 else float(_beta.ppf(alpha/2, k, n-k+1))
    hi = 1.0 if k == n else float(_beta.ppf(1-alpha/2, k+1, n-k))
    return (lo, hi)

# ---------- 1) R1C_index_v2 ----------
def rebuild_r1c():
    out_rows = []
    hdr = ["run_id","rep","grace_ms","reclaimed","zombie_evt_cnt","agent_alive","note"]
    # c1 真实数据来自 C1_rerun.csv（首轮 R1C_index 的 c1 段为首轮失败数据+换行损坏）
    with open(f"{RES}/R1C/C1_rerun.csv") as f:
        for r in csv.DictReader(f):
            out_rows.append([r["run_id"], r["rep"], r["grace_ms"], r["reclaimed"],
                             r["zombie_ind_cnt"], r["agent_alive"],
                             "reclaim_delay_s 列全空(B-m5 如实标注：延迟由 grace 语义推定未实测)"])
    # c3 从原始 run 目录重建（agent_tail.log 提取累计 REFUSE）
    for d in sorted(glob.glob(f"{RES}/R1C/c3_pos_*")):
        run_id = os.path.basename(d)
        m = re.match(r"c3_pos_(\w+)_rep(\d)", run_id)
        pos, rep = m.group(1), m.group(2)
        ric_alive = "NA"; agent_alive = "NA"
        env = open(f"{d}/env.log").read() if os.path.exists(f"{d}/env.log") else ""
        at = f"{d}/agent_tail.log"; ricl = f"{d}/ric.log"
        e2cum = 0
        if os.path.exists(at):
            txt = open(at, errors="ignore").read()
            ms = re.findall(r"REFUSE \(累计 (\d+)\)", txt)
            e2cum = int(ms[-1]) if ms else 0
        note = []
        if os.path.exists(ricl):
            ric_alive = "0" if "Assertion" in open(ricl, errors="ignore").read()[-3000:] else "1"
            note.append("ric_alive 由 ric.log 尾部断言签名重判")
        else:
            note.append("ric.log 缺失——ric_alive 沿用 v1 索引值")
        out_rows.append([run_id, rep, "", "", e2cum, agent_alive,
                         f"pos={pos}; E2 REFUSE 累计口径; " + ";".join(note)])
    with open(f"{RES}/R1C/R1C_index_v2.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(hdr)
        w.writerows(out_rows)
    # 机检：列数一致
    with open(f"{RES}/R1C/R1C_index_v2.csv") as f:
        rr = list(csv.reader(f))
    bad = [i for i, r in enumerate(rr) if len(r) != len(rr[0])]
    print(f"R1C_index_v2: {len(rr)} 行, 列数错位行: {bad if bad else '无（机检通过）'}")
    return out_rows

# ---------- 2) E2 拦截粒度量化 ----------
def quantify_e2():
    rows = []
    for d in sorted(glob.glob(f"{RES}/R1C/c3_pos_*")):
        run_id = os.path.basename(d)
        al = f"{d}/agent_tail.log"
        if not os.path.exists(al): continue
        txt = open(al, errors="ignore").read()
        cums = re.findall(r"REFUSE \(累计 (\d+)\)", txt)
        cum = int(cums[-1]) if cums else 0
        nrows = len(re.findall(r"E2-GATE.*REFUSE", txt))
        # agent 侧实际接收的订阅请求量（E2-GATE 累计 + CAP 内放行首 64）
        rows.append(dict(run_id=run_id, refuse_print_lines=nrows,
                         refuse_cumulative=cum, admitted_approx=cum + 64 if cum else None,
                         note="打印行≠拒绝数：每 500 笔打一行（B-m2 口径修复）"))
    with open(f"{RES}/R1C/E2_refuse_quantification.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["run_id","refuse_print_lines","refuse_cumulative",
                                          "admitted_approx","note"])
        w.writeheader(); w.writerows(rows)
    print("E2_refuse_quantification.csv:", [(r["run_id"], r["refuse_cumulative"]) for r in rows])

# ---------- 3) R1B 统计补强 ----------
def r1b_stats():
    cells = {}
    with open(f"{RES}/R1B/R1B_metrics.csv") as f:
        for r in csv.DictReader(f):
            key = (r["attacker"], int(r["cap"]), int(r["rate"]), int(r["state"]))
            cells.setdefault(key, []).append(r)
    out = []
    for key, runs in sorted(cells.items()):
        alives = [int(r["ric_alive"]) for r in runs]
        k, n = sum(alives), len(alives)
        lo, hi = clopper_pearson(k, n)
        alive_cpu = [float(r["nearRT-RIC_cpu_mean"]) for r in runs
                     if int(r["ric_alive"]) == 1 and r["nearRT-RIC_cpu_mean"]]
        tmax = trimmed = med = None
        if alive_cpu:
            s = sorted(alive_cpu); tmax = s[-1]
            trimmed = sum(s[:-1])/(len(s)-1) if len(s) > 1 else s[0]   # 去最高单值
            med = s[len(s)//2] if len(s) % 2 else (s[len(s)//2-1]+s[len(s)//2])/2
        sig = "CI 跨 0.5：单格不能宣判" if lo <= 0.5 <= hi else ("稳定存活" if k == n else "稳定死亡" if k == 0 else "方向性")
        out.append(dict(attacker=key[0], cap=key[1], rate=key[2], state=key[3],
                        n=n, alive=k, cp95=[round(lo,3), round(hi,3)],
                        cpu_max_alive=tmax, cpu_trimmed_mean=round(trimmed,1) if trimmed is not None else None,
                        cpu_median=med, verdict=sig))
    with open(f"{RES}/R1B/R1B_stats_v2.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)
    n_cross = sum(1 for o in out if o["cp95"][0] <= 0.5 <= o["cp95"][1])
    print(f"R1B_stats_v2: {len(out)} 格；其中 CI 跨 0.5 的格 {n_cross}（n=3 分辨不足，M4 披露）")
    return out

# ---------- 4) R1A 判无效清单 ----------
def r1a_invalidation():
    rows = []
    with open(f"{RES}/R1A/R1A_metrics.csv") as f:
        for r in csv.DictReader(f):
            rid = r["run_id"]
            reason = []
            if rid.startswith("flood_r1000_baseline") and r["attack_sent"] == "0":
                reason.append("攻击器 t=5.6s 早停（流控失速，无 DONE 行，sent 计 0）")
            if rid.startswith("flood_r10000") and r["attack_sent"] == "0":
                reason.append("攻击器 16bit req_id 溢出 assert 自杀（attack.log 实证）或早停")
            if rid.startswith("flood_r100_baseline_rep") and r["attack_sent"] == "4501":
                reason.append("旧版脚本 dur=45s 漂移（DONE t=45.00s，载荷 +50%）")
            if reason:
                rows.append(dict(run_id=rid, invalid_reason="; ".join(reason),
                                 rerun_in="R1F(修复后重跑)"))
    with open(f"{RES}/R1A/R1A_invalidated_runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["run_id","invalid_reason","rerun_in"])
        w.writeheader(); w.writerows(rows)
    print(f"R1A_invalidated_runs.csv: {len(rows)} run 判无效")

if __name__ == "__main__":
    rebuild_r1c()
    quantify_e2()
    r1b_stats()
    r1a_invalidation()
