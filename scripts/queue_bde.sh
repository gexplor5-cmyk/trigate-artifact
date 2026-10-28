#!/bin/bash
# queue_bde.sh — R1C 完成后：R1B 补跑 → R1D → R1E → ALL_DONE
S=/root/trigate_ws/scripts
R=/root/trigate_ws/results
while [ ! -f $R/R1C/DONE_SENTINEL ]; do sleep 30; done
echo "$(date) R1C done, starting R1B(rerun)" >> $R/queue.log
bash $S/run_r1b.sh
echo "$(date) R1B done, starting R1D" >> $R/queue.log
bash $S/run_r1d.sh
echo "$(date) R1D done, starting R1E" >> $R/queue.log
bash $S/run_r1e.sh
echo "$(date) ALL DONE" >> $R/queue.log
touch $R/ALL_DONE
