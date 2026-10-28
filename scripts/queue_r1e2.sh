#!/bin/bash
R=/root/trigate_ws/results
while [ ! -f $R/R1B_CHURN_SENTINEL ]; do sleep 60; done
rm -f $R/R1E/DONE_SENTINEL $R/R1E/fails.txt
bash /root/trigate_ws/scripts/run_r1e.sh
echo "$(date) R1E rerun done" >> $R/queue.log
touch $R/R1E_RERUN_SENTINEL
