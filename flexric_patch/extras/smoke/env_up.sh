#!/bin/bash
# env_up.sh — 启动 FlexRIC 测试环境（RIC + emu_agent_gnb）
# 用法: env_up.sh            # baseline（无闸门）
#       env_up.sh "ENV=V ..."  # 透传给 RIC 的环境变量串（如 "FLEXRIC_SUB_CAP=64 FLEXRIC_RATE_CAP=100"）
FLEXRIC=/root/autodl-tmp/flexric
ENVS="${1:-}"
for p in $(pgrep -x nearRT-RIC); do kill -9 $p 2>/dev/null; done
for p in $(pgrep -x emu_agent_gnb); do kill -9 $p 2>/dev/null; done
sleep 1
rm -f /tmp/ric.log /tmp/agent.log
cd $FLEXRIC
setsid stdbuf -oL -eL env $ENVS ./build/examples/ric/nearRT-RIC -c ./flexric.conf > /tmp/ric.log 2>&1 < /dev/null &
sleep 3
setsid stdbuf -oL -eL ./build/examples/emulator/agent/emu_agent_gnb -c ./flexric.conf > /tmp/agent.log 2>&1 < /dev/null &
sleep 4
if pgrep -x nearRT-RIC > /dev/null && pgrep -x emu_agent_gnb > /dev/null && grep -q "E2 SETUP RESPONSE rx" /tmp/agent.log; then
  echo "ENV_UP_OK ric=$(pgrep -x nearRT-RIC) agent=$(pgrep -x emu_agent_gnb)"
else
  echo "ENV_UP_FAIL"; tail -3 /tmp/ric.log; tail -3 /tmp/agent.log; exit 1
fi
