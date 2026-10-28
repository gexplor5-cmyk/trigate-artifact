#!/usr/bin/env python3
"""R1-D 分析：NC 闭式界标定与 SLA 反推
模型（agent 单线程事件循环=单服务器，rate-latency service curve β(t)=R(t-T)₊）：
  - 每订阅 indication 处理需求：C_ind(us)（实测 [WCET] ind mean/max）
  - 订阅建立成本：C_sub(us)（实测 [WCET] sub_build mean/max）
  - 配置 (P ms 周期, N 条) 的聚合 CPU 速率 ρ = N · C_ind / P   [us CPU / ms]
    即 ρ_us_per_s = N · C_ind · 1000 / P  [us CPU / s] = N·C_ind/P·1e3
  - 突发 σ = N · C_sub（全部订阅同时建立的最坏突发）
  - 界（CPU 占用率，us CPU 消耗 per 秒 / 1e6）：
      U_bound = ρ_us_per_s / 1e6 + σ·f_rebuild / 1e6   （f_rebuild=0 稳态）
    稳态简化：U_bound = N·C_ind/(P·1000)     （无量纲 CPU 比例）
    时延界（单服务器，NC）：D_max = σ/R + T，R=1（单线程满速=1e6 us CPU/s）
  - SLA 反推：给定 CPU 预算 U（如 0.30）→ N_max = floor(U·P·1000/C_ind)
判据核对：
  1) 全部实测点（monitor.csv agent CPU 均值）≤ U_bound × 容差 → 零违例
  2) 紧度 = U_bound / U_meas 的中位数 ≤ 3
  3) ≥1 个 SLA→配额反推工作示例
"""
import csv, json, math, os, statistics as st

RES = "/root/trigate_ws/results/R1D"

def load_index():
    rows = []
    with open(f"{RES}/R1D_index.csv") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows

def agent_cpu_from_monitor(rd, t_skip=15):
    """稳态 CPU%（跳过前 15s 建立期）"""
    path = f"{RES}/{rd}/monitor.csv"
    if not os.path.exists(path): return None, None
    cpu, peak = [], 0.0
    with open(path) as f:
        rd_ = csv.DictReader(f)
        for r in rd_:
            t = float(r["t"])
            if t < t_skip: continue
            v = r.get("emu_agent_gnb_cpu%")
            if v is None or v == "DEAD": continue
            v = float(v); cpu.append(v); peak = max(peak, v)
    if not cpu: return None, None
    return st.mean(cpu), peak

def main():
    rows = load_index()
    points = []
    for r in rows:
        period = float(r["period_ms"]); n = float(r["n_subs"])
        ind_mean = float(r["ind_mean_us"] or 0); ind_max = float(r["ind_max_us"] or 0)
        sub_mean = float(r["sub_build_mean_us"] or 0)
        meas_mean, meas_peak = agent_cpu_from_monitor(r["run_id"])
        # WCET 打点含 sendmsg 系统调用（回环）——理论界用打点值本身
        rho = n * ind_mean * 1000.0 / period / 1e6       # 稳态 CPU 比例（mean 口径）
        rho_max = n * ind_max * 1000.0 / period / 1e6    # WCET 口径界（最坏单次）
        sigma = n * sub_mean / 1e6                        # 突发（一次全建）
        meas = meas_mean / 100.0 if meas_mean is not None else None
        tight = (rho_max / meas) if (meas and meas > 0.001 and rho_max > 0) else None
        points.append(dict(run=r["run_id"], period=period, n=n,
                           ind_mean=ind_mean, ind_max=ind_max, sub_mean=sub_mean,
                           bound_mean_cpu=rho, bound_wcet_cpu=rho_max, sigma=sigma,
                           meas_cpu=meas, meas_peak=meas_peak, tightness=tight,
                           violation=(meas is not None and rho_max < meas - 0.05)))
    # 判据 1：零违例（实测 ≤ WCET 界 + 5pp 容差）
    n_viol = sum(1 for p in points if p["violation"])
    # 判据 2：紧度中位数
    tights = [p["tightness"] for p in points if p["tightness"] is not None and p["tightness"] < 100]
    med_tight = st.median(tights) if tights else None
    # 判据 3：SLA 反推示例（C_ind 取 period=100 档实测均值）
    c100 = [p["ind_mean"] for p in points if p["period"] == 100 and p["ind_mean"] > 0]
    c_ind = st.mean(c100) if c100 else 80.0  # us
    sla_examples = []
    for U in (0.10, 0.30):
        for P in (10, 100, 1000):
            nmax = math.floor(U * P * 1000.0 / c_ind)
            sla_examples.append(dict(sla_cpu=U, period_ms=P, c_ind_us=c_ind, n_max=nmax))
    out = dict(
        points=points,
        n_points=len(points),
        n_violations=n_viol,
        tightness_median=med_tight,
        c_ind_us_100ms=c_ind,
        sla_examples=sla_examples,
        model="U_bound(N,P) = N*C_ind_wcet/(P*1000); D_max = sigma/R + T, R=1e6us/s",
    )
    with open(f"{RES}/R1D_analysis.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: v for k, v in out.items() if k != "points"},
                     indent=2, ensure_ascii=False))
    print(f"points={len(points)} violations={n_viol} tightness_median={med_tight}")

if __name__ == "__main__":
    main()
