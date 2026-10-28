#!/usr/bin/env python3
"""R1-D 分析 v2【M3/B-M5 修复：判据口径全披露】
与 v1 的差异（全部按审稿意见披露）：
  1) 违例判定双口径：字面判据（meas > rho_max 即违例，零容差）与
     实务判据（5 个百分点绝对容差，v1 隐藏口径）并列输出；
  2) tightness=None 的点逐点列出原因（meas 缺失或 meas≈0），n 可判点数明示；
     v1 另有 tightness<100 的过滤（截尾），v2 全量披露分位数与全距；
  3) SLA 反推给 mean 与 WCET 双口径（m4/B-m4 内部不一致修复）；
  4) 紧度报 中位数/全距/P25/P75。
"""
import csv, json, math, os, statistics as st

RES = "/root/trigate_ws/results/R1D"

def load_index():
    with open(f"{RES}/R1D_index.csv") as f:
        return list(csv.DictReader(f))

def agent_cpu_from_monitor(rd, t_skip=15):
    path = f"{RES}/{rd}/monitor.csv"
    if not os.path.exists(path): return None, None
    cpu, peak = [], 0.0
    with open(path) as f:
        for r in csv.DictReader(f):
            if float(r["t"]) < t_skip: continue
            v = r.get("emu_agent_gnb_cpu%")
            if v is None or v in ("", "DEAD"): continue
            v = float(v); cpu.append(v); peak = max(peak, v)
    return (st.mean(cpu), peak) if cpu else (None, None)

def main():
    rows = load_index()
    points = []
    for r in rows:
        period = float(r["period_ms"]); n = float(r["n_subs"])
        ind_mean = float(r["ind_mean_us"] or 0); ind_max = float(r["ind_max_us"] or 0)
        sub_mean = float(r["sub_build_mean_us"] or 0)
        meas_mean, meas_peak = agent_cpu_from_monitor(r["run_id"])
        rho = n * ind_mean * 1000.0 / period / 1e6
        rho_max = n * ind_max * 1000.0 / period / 1e6
        sigma = n * sub_mean / 1e6
        meas = meas_mean / 100.0 if meas_mean is not None else None
        tight = (rho_max / meas) if (meas is not None and meas > 0.001 and rho_max > 0) else None
        tight_none_reason = None
        if tight is None:
            tight_none_reason = "meas缺失(monitor无数据)" if meas is None else "meas≤0.1%(界/实测比无意义)"
        points.append(dict(run=r["run_id"], period=period, n=n,
                           ind_mean=ind_mean, ind_max=ind_max, sub_mean=sub_mean,
                           bound_mean_cpu=rho, bound_wcet_cpu=rho_max, sigma=sigma,
                           meas_cpu=meas, meas_peak=meas_peak, tightness=tight,
                           tightness_none_reason=tight_none_reason,
                           violation_literal=(meas is not None and meas > rho_max),
                           violation_tol5pp=(meas is not None and rho_max < meas - 0.05)))
    viol_lit = [p for p in points if p["violation_literal"]]
    viol_tol = [p for p in points if p["violation_tol5pp"]]
    tights_all = [p["tightness"] for p in points if p["tightness"] is not None]
    n_none = sum(1 for p in points if p["tightness"] is None)
    qs = st.quantiles(tights_all, n=4) if len(tights_all) >= 4 else [None]*3
    out = dict(
        n_points=len(points),
        n_tightness_evaluable=len(tights_all),
        n_tightness_none=n_none,
        tightness_none_points=[p["run"] for p in points if p["tightness"] is None],
        criterion1=dict(
            literal=dict(n_violations=len(viol_lit),
                         violators=[dict(run=p["run"], meas=p["meas_cpu"],
                                         bound_wcet=p["bound_wcet_cpu"],
                                         excess_abs_pp=round((p["meas_cpu"]-p["bound_wcet_cpu"])*100, 3))
                                    for p in viol_lit]),
            tol5pp=dict(n_violations=len(viol_tol),
                        violators=[p["run"] for p in viol_tol],
                        note="5 个百分点绝对容差（v1 未披露口径）"),
        ),
        tightness=dict(median=st.median(tights_all) if tights_all else None,
                       p25=qs[0], p75=qs[2], min=min(tights_all), max=max(tights_all),
                       note="v1 仅报中位数且暗含 <100 截尾；v2 全量披露"),
        sla=dict(
            c_ind_mean_us_100ms=st.mean([p["ind_mean"] for p in points
                                         if p["period"] == 100 and p["ind_mean"] > 0]),
            c_ind_wcet_us=max(p["ind_max"] for p in points if p["ind_max"] > 0),
            examples=[],
            note="m4 修复：容量规划双口径——mean 口径系统性高估 N_max，WCET 口径为保守设计值"),
    )
    for U in (0.10, 0.30):
        for P in (10, 100, 1000):
            nmax_mean = math.floor(U * P * 1000.0 / out["sla"]["c_ind_mean_us_100ms"])
            nmax_wcet = math.floor(U * P * 1000.0 / out["sla"]["c_ind_wcet_us"])
            out["sla"]["examples"].append(dict(sla_cpu=U, period_ms=P,
                                               n_max_mean=nmax_mean, n_max_wcet=nmax_wcet))
    out["model"] = ("U_bound(N,P) = N*C_ind_wcet/(P*1000); D_max = sigma/R + T, R=1e6us/s; "
                    "v2 口径全披露（容差/None 点/全距/双口径 SLA）")
    with open(f"{RES}/R1D_analysis_v2.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: v for k, v in out.items() if k != "points"},
                     indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
