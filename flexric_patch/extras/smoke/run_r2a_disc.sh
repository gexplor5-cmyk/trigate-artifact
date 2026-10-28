#!/bin/bash
# R2-A 判别实验：b1 行缓冲捕获崩溃前最后 SDK 消息（H-A/H-B/H-C 判别）
set -u
FLEXRIC=/root/autodl-tmp/flexric
OUT=/root/trigate_ws/results/R2A/disc
ASYNC=$FLEXRIC/build/examples/xApp/c/kpm_rc/xapp_async
BENIGN=$FLEXRIC/build/examples/xApp/c/kpm_rc/xapp_benign
mkdir -p $OUT
for REP in 1 2 3; do
  RD=$OUT/rep$REP; mkdir -p $RD
  $FLEXRIC/smoke/env_up.sh "FLEXRIC_L1=1 FLEXRIC_L1_RHO=100 FLEXRIC_L1_SIGMA=64 FLEXRIC_L1_CAP=64 FLEXRIC_SUB_CAP=64 FLEXRIC_RATE_CAP=100" > $RD/env.log 2>&1
  RICPID=$(pgrep -x nearRT-RIC)
  sleep 1
  setsid stdbuf -oL -eL $BENIGN b1 > $RD/benign1.log 2>&1 < /dev/null &
  sleep 4
  setsid stdbuf -oL -eL $BENIGN b2 > $RD/benign2.log 2>&1 < /dev/null &
  sleep 4
  FLEXRIC_SYNC_WAIT_MS=0 FLEXRIC_PENDING_TIMEOUT_MS=86400000 FLEXRIC_SNDTIMEO_MS=100 \
    timeout -k 5 28 $ASYNC churn 0 20 60 > $RD/attack.log 2>&1
  sleep 3
  for p in $(pgrep -x xapp_async); do kill -9 $p 2>/dev/null; done
  sleep 5
  tail -c 3000000 /tmp/ric.log > $RD/ric_tail.log
  for p in $(pgrep -f xapp_benign); do kill -9 $p 2>/dev/null; done
  for p in $(pgrep -x nearRT-RIC); do kill -9 $p 2>/dev/null; done
  for p in $(pgrep -x emu_agent_gnb); do kill -9 $p 2>/dev/null; done
  echo "== rep$REP b1 tail =="; tail -6 $RD/benign1.log
  sleep 2
done
