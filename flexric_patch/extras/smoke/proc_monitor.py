#!/usr/bin/env python3
"""smoke test：采样进程 CPU% 与 RSS(KB)，CSV 输出到 stdout。
用法: proc_monitor.py <pid1> [<pid2> ...]  — 每秒一行，Ctrl-C/Ctrl-D 结束
"""
import sys, time, os

pids = [int(p) for p in sys.argv[1:]]
names = {}
for p in pids:
    try:
        with open(f"/proc/{p}/comm") as f: names[p] = f.read().strip()
    except Exception: names[p] = f"pid{p}"

prev = {p: None for p in pids}
t0 = time.time()
print("t," + ",".join(f"{names[p]}_cpu%,{names[p]}_rssKB" for p in pids), flush=True)
while True:
    row = [f"{time.time()-t0:.1f}"]
    alive = False
    for p in pids:
        try:
            with open(f"/proc/{p}/stat") as f: fields = f.read().rsplit(")", 1)[1].split()
            utime, stime = int(fields[11]), int(fields[12])
            total_ticks = utime + stime
            with open(f"/proc/{p}/status") as f:
                rss = [l for l in f if l.startswith("VmRSS")][0].split()[1]
            alive = True
        except Exception:
            row.append("DEAD,DEAD"); continue
        if prev[p] is None: cpu = 0.0
        else: cpu = (total_ticks - prev[p]) / os.sysconf("SC_CLK_TCK") * 100.0
        prev[p] = total_ticks
        row.append(f"{cpu:.1f},{rss}")
    print(",".join(row), flush=True)
    if not alive: break
    time.sleep(1.0)
