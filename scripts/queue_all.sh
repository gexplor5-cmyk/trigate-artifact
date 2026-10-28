#!/bin/bash
# queue_all.sh — R1 实验总控：等 R1A 哨兵 → 依次 R1B → R1C → R1D（环境互斥串行）
S=/root/trigate_ws/scripts
R=/root/trigate_ws/results
while [ ! -f $R/R1A/DONE_SENTINEL ]; do sleep 30; done
echo "$(date) R1A done, starting R1B" >> $R/queue.log
bash $S/run_r1b.sh
echo "$(date) R1B done, starting R1C" >> $R/queue.log
bash $S/run_r1c.sh
echo "$(date) R1C done, starting R1D" >> $R/queue.log
bash $S/run_r1d.sh
echo "$(date) ALL QUEUES DONE" >> $R/queue.log
touch $R/ALL_DONE
