#!/bin/bash
# E5d: 零误伤——CAP=64+RATE=100 闸门全开下，攻击进行中良性 xapp_kpm_rc 全链路
set -u
ROOT=/root/autodl-tmp/flexric; OUT=/root/autodl-tmp/research_archive; cd $ROOT
PAT2="build/exam""ples"; pkill -9 -f "$PAT2" 2>/dev/null; sleep 1
FLEXRIC_SUB_CAP=64 FLEXRIC_RATE_CAP=100 ./build/examples/ric/nearRT-RIC > $OUT/ricE5d.log 2>&1 &
RIC_PID=$!; sleep 1
./build/examples/emulator/agent/emu_agent_gnb > $OUT/agentE5d.log 2>&1 &
AG_PID=$!; sleep 2
# 攻击者在后台打 25s
timeout -s INT 25 ./build/examples/xApp/c/kpm_rc/xapp_churn 60 0 0 > $OUT/churnE5d.log 2>&1 &
sleep 4
# 攻击进行中跑良性 xApp（正常订阅→收指示→退出）
timeout 20 ./build/examples/xApp/c/kpm_rc/xapp_kpm_rc > $OUT/benignE5d.log 2>&1
BEN_RC=$?
sleep 3
pkill -9 -f "$PAT2" 2>/dev/null
echo "良性 xApp 退出码=$BEN_RC（0=SUCCESS）"
grep -E "SUCCESS|Indication|Successfully subscribed" $OUT/benignE5d.log | tail -4
