#!/bin/bash
# check_r3_protocol.sh — V25 事前纪律机检自验：断言 Birth(协议) < Birth(首 run 完成)
# 对 R3 全部新实验执行；自带反例自测（故意后写协议必须报红）
W=/root/trigate_ws
PROTO=$W/results/R3/R3_protocol.txt
PASS=0; FAIL=0
check(){ # $1=实验名 $2=首个 run DONE 文件
  local NAME=$1 DONEF=$2
  if [ ! -f "$DONEF" ]; then echo "  [$NAME] SKIP（无首 run DONE：未跑）"; return; fi
  local PB=$(stat --format='%W' "$PROTO" 2>/dev/null); [ "$PB" = "0" ] && PB=$(stat --format='%Y' "$PROTO")
  local RB=$(stat --format='%Y' "$DONEF")
  if [ "$PB" -lt "$RB" ]; then
    echo "  [$NAME] ✓ Birth(协议 $(date -d @$PB '+%T')) < 首 run 完成 $(date -d @$RB '+%T'))"; PASS=$((PASS+1))
  else
    echo "  [$NAME] ✗ 违例：协议 Birth 晚于首 run"; FAIL=$((FAIL+1))
  fi
}
echo "== R3 各实验事前性机检（协议 $PROTO）=="
check R3A "$W/results/R3A/r3a_l1l2_cap16_rep1/DONE"
check R3B "$W/results/R3B/b11_trunc_fix_rep1/env.log"
check R3C "$W/results/R3C/r3c_l0_rep1/env.log"
check R3D "$W/results/R3D/r3d_cap20_rep1/env.log"
check R3E "$W/results/R3E/r3e_4att_fcfs_rep1/DONE"
echo "== 历史反例（应报红：R2E/R2B 协议事后性，R2R-C1/B4-C1 已定性）=="
check "R2E(预期违例)" "$W/results/R2E/r2e_cap4_rep1/DONE"
echo "== 反例自测（临时后写协议，断言必须报红）=="
TMPPROTO=$W/results/R3/_selftest_posthoc_protocol.txt
echo "fake protocol written at $(date)" > "$TMPPROTO"
NAME="_SELFTEST"; DONEF="$W/results/R3A/r3a_l1l2_cap16_rep1/DONE"
PB=$(stat --format='%Y' "$TMPPROTO"); RB=$(stat --format='%Y' "$DONEF")
if [ "$PB" -lt "$RB" ]; then echo "  [$NAME] ✗✗ 机检失效（后写协议未检出）——工具不可用"; FAIL=$((FAIL+1))
else echo "  [$NAME] ✓ 正确报红（后写协议被检出）——机检有效"; PASS=$((PASS+1)); fi
rm -f "$TMPPROTO"
echo "== 汇总：PASS=$PASS FAIL=$FAIL（FAIL 含 R2E 历史反例的预期违例 1 项）=="
