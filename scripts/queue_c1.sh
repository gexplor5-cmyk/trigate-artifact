#!/bin/bash
R=/root/trigate_ws/results
while [ ! -f $R/ALL_DONE ]; do sleep 60; done
bash /root/trigate_ws/scripts/rerun_c1.sh
touch $R/C1_RERUN_SENTINEL
