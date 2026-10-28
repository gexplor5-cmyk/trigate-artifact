#!/bin/bash
# rerun_c1.sh — R1-C C1（租约回收）补跑：仅 c1_lease 12 run（新 agent 二进制含 lease 必经路径钩子）
set -u
FLEXRIC=/root/autodl-tmp/flexric
OUT=/root/trigate_ws/results/R1C
echo "run_id,rep,grace_ms,reclaimed,zombie_ind_cnt,rss_after,agent_alive,reclaim_delay_s" >> $OUT/C1_rerun.csv
for GRACE in 0 1000 2000 5000; do
for REP in 1 2 3; do
  RUN_ID="c1_lease_${GRACE}_rep${REP}"
  RD=$OUT/${RUN_ID}_v2; mkdir -p $RD
  $FLEXRIC/smoke/env_up.sh "" > $RD/env.log 2>&1 || { echo "$RUN_ID ENV_FAIL" >> $OUT/fails.txt; continue; }
  for p in $(pgrep -x emu_agent_gnb); do kill -9 $p; done; sleep 1
  setsid stdbuf -oL -eL env FLEXRIC_AGENT_GRACE_MS=$GRACE $FLEXRIC/build/examples/emulator/agent/emu_agent_gnb -c $FLEXRIC/flexric.conf > /tmp/agent.log 2>&1 < /dev/null &
  sleep 4
  AGPID=$(pgrep -x emu_agent_gnb)
  python3 $FLEXRIC/smoke/proc_monitor.py $AGPID > $RD/monitor.csv 2>/dev/null &
  MONPID=$!
  FLEXRIC_SYNC_WAIT_MS=5000 FLEXRIC_PENDING_TIMEOUT_MS=30000 \
    setsid $FLEXRIC/build/examples/xApp/c/kpm_rc/xapp_wcet 20 100 > $RD/wcet.log 2>&1 < /dev/null &
  WCPID=$!
  sleep 12
  RICPID=$(pgrep -x nearRT-RIC)
  kill -9 $RICPID 2>/dev/null
  T0=$(date +%s.%N)
  # 轮询 agent 日志等待回收行（≤15s）
  RECLAIMED=0; DELAY=""
  for i in $(seq 1 30); do
    if grep -q "回收 [0-9]* 条订阅" /tmp/agent.log 2>/dev/null; then
      RECLAIMED=$(awk '/到期.*回收/{match($0,/回收 [0-9]+/); print substr($0,RSTART+3,RLENGTH-3)}' /tmp/agent.log | tail -1)
      T1=$(date +%s.%N); DELAY=$(echo "$T1 - $T0" | bc)
      break
    fi
    sleep 0.5
  done
  sleep 3
  kill $MONPID 2>/dev/null; kill -9 $WCPID 2>/dev/null
  ZOMBIE=$(awk '/no xApp associated|Communication with/{c++} END{print c+0}' /tmp/agent.log)
  [ -z "$(pgrep -x emu_agent_gnb)" ] && AA=0 || AA=1
  cp /tmp/agent.log $RD/agent.log
  echo "$RUN_ID,$REP,$GRACE,${RECLAIMED:-0},$ZOMBIE,,$AA,${DELAY:-}" >> $OUT/C1_rerun.csv
  echo "$RUN_ID grace=$GRACE reclaimed=${RECLAIMED:-0} delay=${DELAY:-na}s zombie_evt=$ZOMBIE alive=$AA" >> $OUT/progress.log
  for p in $(pgrep -x emu_agent_gnb); do kill -9 $p 2>/dev/null; done
  for p in $(pgrep -x nearRT-RIC); do kill -9 $p 2>/dev/null; done
  sleep 1
done
done
echo "C1_RERUN_DONE" >> $OUT/progress.log
