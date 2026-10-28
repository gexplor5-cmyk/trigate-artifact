#!/usr/bin/env python3
# R3B/R3E 全口径列补提（M5/B5-m5/m4 处置）：从 run 目录原始日志重提
# run_r2e 18 列口径的缺失列（done_t/sent/delivered/peak/cpu_trim/rss_peak）
# 输出 R3B_raw_v2.csv / R3E_raw_v2.csv（保留原列不动，追加补提列）
import csv, os, re, glob

W='/root/trigate_ws'

def parse_attack(path):
    """DONE 行与 ops_rate 峰值（xapp_async 口径）"""
    if not os.path.exists(path) or os.path.getsize(path)==0: return None
    last=None; peak=0
    for line in open(path,errors='ignore'):
        m=re.search(r'\[async\] DONE t=([0-9.]+)s subs=(\d+) dels=(\d+) .*total=(\d+)',line)
        if m: last=dict(t=float(m.group(1)),total=int(m.group(4)))
        m2=re.search(r'ops_rate=(\d+)/s',line)
        if m2: peak=max(peak,int(m2.group(1)))
    return (last,peak) if last else (None,peak)

def monitor_stats(path):
    rows=[r for r in csv.reader(open(path)) if r and r[0]!='t']
    try:
        w=[float(r[1]) for r in rows if float(r[0])>=11.0 and r[1] not in ('','DEAD') and r[1]!='nearRT-RIC_cpu%']
    except (ValueError,IndexError):
        w=[]
    if not w: return dict(cpu_mean=0,cpu_trim=0,cpu_peak=0,rss_peak=0,n=0)
    rss=[]
    for r in rows:
        try: rss.append(float(r[2]))
        except (ValueError,IndexError): pass
    mean=sum(w)/len(w); trim=(sum(w[:-1])/(len(w)-1)) if len(w)>1 else mean
    return dict(cpu_mean=round(mean,1),cpu_trim=round(trim,1),cpu_peak=max(w),rss_peak=max(rss) if rss else 0,n=len(w))

# ---- R3B ----
out=[]
for row in csv.DictReader(open(f'{W}/results/R3B/R3B_raw.csv')):
    rd=f"{W}/results/R3B/{row['run_id']}"
    al=f'{rd}/attack.log'
    last,peak=parse_attack(al) or (None,0)
    ms=monitor_stats(f'{rd}/monitor.csv')
    row2=dict(row)
    row2['done_t']='NA' if last is None else last['t']
    row2['sent']='NA' if last is None else last['total']
    row2['peak']='NA' if not peak else peak
    row2.update({f'reex_{k}':v for k,v in ms.items()})
    out.append(row2)
keys=list(out[0].keys())
with open(f'{W}/results/R3B/R3B_raw_v2_reextract.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=keys); w.writeheader(); w.writerows(out)

# ---- R3E（4 攻击器合并口径）----
out=[]
for row in csv.DictReader(open(f'{W}/results/R3E/R3E_raw.csv')):
    rd=f"{W}/results/R3E/{row['run_id']}"
    tot=0; dt=0.0; peak=0; nlog=0
    for al in sorted(glob.glob(f'{rd}/attack*.log')):
        r=parse_attack(al)
        if r and r[0]:
            tot+=r[0]['total']; dt+=r[0]['t']; nlog+=1
        if r: peak=max(peak,r[1])
    ms=monitor_stats(f'{rd}/monitor.csv')
    row2=dict(row)
    row2['done_t_sum4']=round(dt,2) if nlog else 'NA'
    row2['sent_sum4']=tot if nlog else 'NA'
    row2['peak']=peak if peak else 'NA'
    row2['n_attack_logs_done']=nlog
    row2.update({f'reex_{k}':v for k,v in ms.items()})
    out.append(row2)
keys=list(out[0].keys())
with open(f'{W}/results/R3E/R3E_raw_v2_reextract.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=keys); w.writeheader(); w.writerows(out)

print("R3B v2:", len(out))
for r in out[:3]: print(' ', r['run_id'], r['done_t'], r['sent'], r['reex_cpu_trim'], r['reex_rss_peak'])
import collections
print("R3E v2:")
for r in csv.DictReader(open(f'{W}/results/R3E/R3E_raw_v2_reextract.csv')):
    print(' ', r['run_id'], r['done_t_sum4'], r['sent_sum4'], r['peak'], r['reex_cpu_trim'], r['reex_rss_peak'])
