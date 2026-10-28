#!/usr/bin/env python3
"""R1-A/R1-B metrics 后处理：从每 run monitor.csv 提取攻击窗口 CPU/RSS"""
import csv, os, statistics as st
import sys

def proc_dir(res_dir, idx_csv, out_csv, t_start=8.0, t_end=45.0, cols=("ric","agent")):
    """攻击窗口 ≈ [t_start, t_end]（启动 2s+benign 期后→攻击 30s+kill 后）"""
    rows_out = []
    with open(idx_csv) as f:
        idx = list(csv.DictReader(f))
    # v1/v2 列名归一（cap,rate_cap → gate）
    for r in idx:
        if not r.get("run_id") and r.get("attacker"):
            # v1 首行脏数据兜底：跳过空 run_id
            continue
        if "gate" not in r or not r.get("gate"):
            cap = r.get("cap", "")
            rc = r.get("rate_cap", "")
            if cap == "0" and rc in ("", "0"): r["gate"] = "baseline"
            elif cap != "0" and rc not in ("", "0"): r["gate"] = "caprate"
            elif cap != "0": r["gate"] = "cap"
            else: r["gate"] = "rate"
    idx = [r for r in idx if r.get("run_id")]
    for r in idx:
        rid = r.get("run_id") or r.get("run_id")
        mpath = os.path.join(res_dir, rid, "monitor.csv")
        if not os.path.exists(mpath):
            continue
        stats = {}
        with open(mpath) as f:
            for row in csv.DictReader(f):
                t = float(row["t"])
                if t < t_start or t > t_end:
                    continue
                for k in row:
                    if k == "t": continue
                    v = row[k]
                    if v in ("DEAD", ""): continue
                    if "_cpu%" in k:
                        stats.setdefault(k, []).append(float(v))
                    elif "_rssKB" in k:
                        stats.setdefault(k + "_list", []).append(float(v))
        out = dict(run_id=rid)
        for k, vals in stats.items():
            if k.endswith("_list"):
                name = k[:-5]
                out[name + "_rss_peak_kb"] = max(vals)
            else:
                base = k.replace("_cpu%", "")
                out[base + "_cpu_mean"] = round(st.mean(vals), 1)
                out[base + "_cpu_peak"] = max(vals)
        rows_out.append((r, out))
    # 合并 index+metrics 输出
    allkeys = []
    for _, o in rows_out:
        for k in o:
            if k not in allkeys: allkeys.append(k)
    hdr = list(idx[0].keys()) + [k for k in allkeys if k != "run_id"]
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=hdr, extrasaction="ignore")
        w.writeheader()
        for r, o in rows_out:
            r2 = dict(r); r2.update(o)
            w.writerow(r2)
    print(f"merged {len(rows_out)} runs -> {out_csv}")

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "A"
    R = "/root/trigate_ws/results"
    if which == "A":
        proc_dir(f"{R}/R1A", f"{R}/R1A/R1A_raw.csv", f"{R}/R1A/R1A_metrics.csv")
    else:
        # R1B：monitor 起点后 t≈2-32 为攻击窗（kill 后 8s 恢复在 32-44）
        proc_dir(f"{R}/R1B", f"{R}/R1B/R1B_index.csv", f"{R}/R1B/R1B_metrics.csv",
                 t_start=3.0, t_end=23.0)
