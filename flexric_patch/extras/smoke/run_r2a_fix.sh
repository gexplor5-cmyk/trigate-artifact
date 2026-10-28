#!/bin/bash
# R2-A 修复对照矩阵：{A, B, AB} × churn l1l2 × 3 rep
# A = FLEXRIC_PATCH5_SDK=1（xApp SDK pending-miss 容错）→ 只给良性 xApp
# B = FLEXRIC_FIX_EQ_XAPPID=1 + FLEXRIC_MAP_COLLISION_SAFE=1（RIC 侧根因修复）
# 判据三问：b1 存活？b1 订阅保住（ind 增量）？b2 同样？
set -u
FLEXRIC=/root/autodl-tmp/flexric
OUT=/root/trigate_ws/results/R2A/fix
ASYNC=$FLEXRIC/build/examples/xApp/c/kpm_rc/xapp_async
BENIGN=$FLEXRIC/build/examples/xApp/c/kpm_rc/xapp_benign
mkdir -p $OUT
echo "cfg,rep,b1_alive,b2_alive,b1_ind,b2_ind,b1_sub_ok,b2_sub_ok" > $OUT/fix_matrix.csv
for CFG in A B AB; do
for REP in 1 2 3; do
  RD=$OUT/${CFG}_rep$REP; mkdir -p $RD
  case $CFG in
    A)  RICENV="FLEXRIC_L1=1 FLEXRIC_L1_RHO=100 FLEXRIC_L1_SIGMA=64 FLEXRIC_L1_CAP=64 FLEXRIC_SUB_CAP=64 FLEXRIC_RATE_CAP=100"; BENV="FLEXRIC_PATCH5_SDK=1 FLEXRIC_XAPP_PENDTO_TOLERANT=1";;
    B)  RICENV="FLEXRIC_L1=1 FLEXRIC_L1_RHO=100 FLEXRIC_L1_SIGMA=64 FLEXRIC_L1_CAP=64 FLEXRIC_SUB_CAP=64 FLEXRIC_RATE_CAP=100 FLEXRIC_FIX_EQ_XAPPID=1 FLEXRIC_MAP_COLLISION_SAFE=1"; BENV="";;
    AB) RICENV="FLEXRIC_L1=1 FLEXRIC_L1_RHO=100 FLEXRIC_L1_SIGMA=64 FLEXRIC_L1_CAP=64 FLEXRIC_SUB_CAP=64 FLEXRIC_RATE_CAP=100 FLEXRIC_FIX_EQ_XAPPID=1 FLEXRIC_MAP_COLLISION_SAFE=1"; BENV="FLEXRIC_PATCH5_SDK=1 FLEXRIC_XAPP_PENDTO_TOLERANT=1";;
  esac
  $FLEXRIC/smoke/env_up.sh "$RICENV" > $RD/env.log 2>&1
  sleep 1
  setsid stdbuf -oL -eL env $BENV $BENIGN b1 > $RD/benign1.log 2>&1 < /dev/null &
  sleep 4
  setsid stdbuf -oL -eL env $BENV $BENIGN b2 > $RD/benign2.log 2>&1 < /dev/null &
  sleep 4
  FLEXRIC_SYNC_WAIT_MS=0 FLEXRIC_PENDING_TIMEOUT_MS=86400000 FLEXRIC_SNDTIMEO_MS=100 \
    timeout -k 5 28 $ASYNC churn 0 20 60 > $RD/attack.log 2>&1
  sleep 3
  for p in $(pgrep -x xapp_async); do kill -9 $p 2>/dev/null; done
  sleep 8
  B1A=0; B2A=0
  pgrep -f "xapp_benign b1" > /dev/null && B1A=1
  pgrep -f "xapp_benign b2" > /dev/null && B2A=1
  IND1=$(awk '/indications total=/{match($0,/total=[0-9]+/); v=substr($0,RSTART+6,RLENGTH-6)} END{print v+0}' $RD/benign1.log)
  IND2=$(awk '/indications total=/{match($0,/total=[0-9]+/); v=substr($0,RSTART+6,RLENGTH-6)} END{print v+0}' $RD/benign2.log)
  SOK1=$(grep -c "subscribed OK" $RD/benign1.log); SOK2=$(grep -c "subscribed OK" $RD/benign2.log)
  tail -c 3000000 /tmp/ric.log > $RD/ric_tail.log
  for p in $(pgrep -f xapp_benign); do kill -9 $p 2>/dev/null; done
  for p in $(pgrep -x nearRT-RIC); do kill -9 $p 2>/dev/null; done
  for p in $(pgrep -x emu_agent_gnb); do kill -9 $p 2>/dev/null; done
  echo "$CFG,$REP,$B1A,$B2A,$IND1,$IND2,$SOK1,$SOK2" >> $OUT/fix_matrix.csv
  echo "[$CFG rep$REP] b1=$B1A b2=$B2A ind1=$IND1 ind2=$IND2" 
  sleep 2
done
done
touch $OUT/DONE
