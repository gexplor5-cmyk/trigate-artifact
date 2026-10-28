#!/bin/bash
R=/root/trigate_ws/results
while [ ! -f $R/ALL_DONE ]; do sleep 60; done
bash /root/trigate_ws/scripts/run_r1e.sh
echo "$(date) R1E done" >> $R/queue.log
