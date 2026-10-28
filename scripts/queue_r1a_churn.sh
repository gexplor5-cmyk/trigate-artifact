#!/bin/bash
R=/root/trigate_ws/results
# 等 c1 补跑完（它是最后入队的）——挂 ALL_DONE 之后跑，再跑完 R1A churn
while [ ! -f $R/C1_RERUN_SENTINEL ]; do sleep 60; done
bash /root/trigate_ws/scripts/run_r1a.sh
echo "$(date) R1A churn rerun done" >> $R/queue.log
touch $R/R1A_CHURN_SENTINEL
