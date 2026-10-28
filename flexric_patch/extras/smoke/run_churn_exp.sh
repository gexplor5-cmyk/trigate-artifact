#!/bin/bash
# smoke test第2轮 · E5 系列：间歇性建删循环（churn）攻击三组对照
# 用法: run_churn_exp.sh <场景名> <SUB_CAP> <RATE_CAP> <攻击时长s> [batch] [良性xApp开关1/0]
set -u
SCENE=$1; SUB_CAP=$2; RATE_CAP=$3; DUR=$4; BATCH=${5:-60}; BENIGN=${6:-0}
ROOT=/root/autodl-tmp/flexric
OUT=/root/autodl-tmp/research_archive
cd $ROOT

# 清场
pkill -f nearRT-RIC 2>/dev/null; pkill -f emu_agent_gnb 2>/dev/null; pkill -f xapp_churn 2>/dev/null
pkill -f xapp_kpm_rc 2>/dev/null; sleep 1

# 1. 起 RIC（闸门环境变量）
FLEXRIC_SUB_CAP=$SUB_CAP FLEXRIC_RATE_CAP=$RATE_CAP ./build/examples/ric/nearRT-RIC > $OUT/ricE5$SCENE.log 2>&1 &
RIC_PID=$!
sleep 1
# 2. 起 E2 agent
./build/examples/emulator/agent/emu_agent_gnb > $OUT/agentE5$SCENE.log 2>&1 &
AG_PID=$!
sleep 2
# 3. 采样器（RIC + agent）
python3 smoke/proc_monitor.py $RIC_PID $AG_PID > $OUT/E5${SCENE}_monitor.csv &
MON_PID=$!
sleep 3
# 4. 良性 xApp（可选，零误伤验证）
if [ "$BENIGN" = "1" ]; then
  timeout $DUR ./build/examples/xApp/c/kpm_rc/xapp_kpm_rc > $OUT/benignE5$SCENE.log 2>&1 &
fi
# 5. churn 攻击（限时自灭，发 SIGTERM 优雅收尾再强杀）
timeout -s INT $DUR ./build/examples/xApp/c/kpm_rc/xapp_churn $BATCH 0 0 > $OUT/churnE5$SCENE.log 2>&1 &
CH_PID=$!
# 等攻击结束（timeout 保证）
wait $CH_PID 2>/dev/null
sleep 5   # 收尾窗口
# 6. 停采样与全链
kill $MON_PID 2>/dev/null
pkill -f xapp_kpm_rc 2>/dev/null; pkill -f emu_agent_gnb 2>/dev/null; pkill -INT -f nearRT-RIC 2>/dev/null; sleep 2; pkill -9 -f nearRT-RIC 2>/dev/null
echo "[E5$SCENE] 完成: SUB_CAP=$SUB_CAP RATE_CAP=$RATE_CAP DUR=${DUR}s batch=$BATCH benign=$BENIGN"
echo "  RIC存活: $(if kill -0 $RIC_PID 2>/dev/null; then echo YES; else echo NO-CRASHED; fi)"
grep -c "REFUSE" $OUT/ricE5$SCENE.log | xargs echo "  REFUSE打印行数:"
tail -3 $OUT/churnE5$SCENE.log
