#!/bin/bash
# B11 快速验证：L1 满表 LRU + fail-closed（churn 全速 12s×3 rep）
set -u
FLEXRIC=/root/autodl-tmp/flexric
W=/root/trigate_ws
OUT=$W/results/B11; mkdir -p $OUT
echo "rep,b1_alive,b2_alive,b1_ind,b2_ind,l1drop,failclosed_drop,full_reject,cpu" > $OUT/b11_quick.csv
for REP in 1 2 3; do
  RD=$OUT/rep$REP; mkdir -p $RD
  $FLEXRIC/smoke/env_up.sh "FLEXRIC_L1=1 FLEXRIC_L1_RHO=100 FLEXRIC_L1_SIGMA=64 FLEXRIC_L1_CAP=64 FLEXRIC_L1_FULLPOLICY=lru FLEXRIC_L1_FAILCLOSED=1 FLEXRIC_FIX_EQ_XAPPID=1 FLEXRIC_MAP_COLLISION_SAFE=1" > $RD/env.log 2>&1
  sleep 1
  setsid stdbuf -oL -eL env FLEXRIC_PATCH5_SDK=1 FLEXRIC_XAPP_PENDTO_TOLERANT=1 $FLEXRIC/build/examples/xApp/c/kpm_rc/xapp_benign b1 > $RD/benign1.log 2>&1 < /dev/null &
  sleep 4
  setsid stdbuf -oL -eL env FLEXRIC_PATCH5_SDK=1 FLEXRIC_XAPP_PENDTO_TOLERANT=1 $FLEXRIC/build/examples/xApp/c/kpm_rc/xapp_benign b2 > $RD/benign2.log 2>&1 < /dev/null &
  sleep 4
  RICPID=$(pgrep -x nearRT-RIC)
  python3 $FLEXRIC/smoke/proc_monitor.py $RICPID > $RD/monitor.csv 2>/dev/null &
  MON=$!
  sleep 2
  I1B=$(awk '/indications total=/{match($0,/total=[0-9]+/);v=substr($0,RSTART+6,RLENGTH-6)}END{print v+0}' $RD/benign1.log)
  I2B=$(awk '/indications total=/{match($0,/total=[0-9]+/);v=substr($0,RSTART+6,RLENGTH-6)}END{print v+0}' $RD/benign2.log)
  FLEXRIC_SYNC_WAIT_MS=0 FLEXRIC_PENDING_TIMEOUT_MS=86400000 FLEXRIC_SNDTIMEO_MS=100 \
    timeout -k 3 16 $FLEXRIC/build/examples/xApp/c/kpm_rc/xapp_async churn 0 12 60 > $RD/attack.log 2>&1
  sleep 6
  I1A=$(awk '/indications total=/{match($0,/total=[0-9]+/);v=substr($0,RSTART+6,RLENGTH-6)}END{print v+0}' $RD/benign1.log)
  I2A=$(awk '/indications total=/{match($0,/total=[0-9]+/);v=substr($0,RSTART+6,RLENGTH-6)}END{print v+0}' $RD/benign2.log)
  B1=0;B2=0; pgrep -f "xapp_benign b1">/dev/null&&B1=1; pgrep -f "xapp_benign b2">/dev/null&&B2=1
  L1D=$(grep -oE "\[L1\].*累计=[0-9]+" /tmp/ric.log|tail -1|grep -oE "[0-9]+$");L1D=${L1D:-0}
  FCD=$(grep -cE "malformed procedureCode" /tmp/ric.log)
  FRJ=$(grep -cE "关联表满" /tmp/ric.log)
  CPU=$(python3 -c "
import csv
rows=[r for r in csv.reader(open('$RD/monitor.csv')) if r and r[0]!='t']
w=[float(r[1]) for r in rows if float(r[0])>=9 and r[1] not in('','DEAD')]
print('%.1f'%(sum(w)/len(w)) if w else 0)")
  tail -c 2000000 /tmp/ric.log > $RD/ric_tail.log
  echo "$REP,$B1,$B2,$((I1A-I1B)),$((I2A-I2B)),$L1D,$FCD,$FRJ,$CPU" >> $OUT/b11_quick.csv
  kill $MON 2>/dev/null
  for p in $(pgrep -f xapp_benign; pgrep -x nearRT-RIC; pgrep -x emu_agent_gnb; pgrep -x xapp_async); do kill -9 $p 2>/dev/null; done
  sleep 1
done
touch $OUT/DONE
