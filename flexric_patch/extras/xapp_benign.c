/*
 * xapp_benign.c — R1-B/R1-A 良性负载 xApp（长驻，零误伤观测）
 *
 * ColO-RAN 部署画像合成（数据集无订阅参数级画像——从 TMC'23 实验配置与
 * OSC kpimon 模板合成的订阅参数，如实标注）：每个实例模拟一个 kpimon 类
 * 良性 xApp：KPM ran_func=2、report period=100ms、3GPP TS 28.552 七项
 * gNB metrics（与官方 xapp_kpm_moni 相同订阅参数）。
 *
 * 与 xapp_kpm_moni 的差别：不自动删除/退出——长驻订阅+每 5s 打印
 * indication 累计计数（零误伤判据：计数持续线性增长 = 无断流）。
 *
 * 用法: xapp_benign [label]      （Ctrl-C 退出时打印汇总）
 */
#include "../../../../src/xApp/e42_xapp_api.h"
#include "../../../../src/util/alg_ds/alg/defer.h"
#include "../../../../src/util/time_now_us.h"

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <stdatomic.h>

static
kpm_event_trigger_def_t gen_ev_trig(uint64_t period)
{
  kpm_event_trigger_def_t dst = {0};
  dst.type = FORMAT_1_RIC_EVENT_TRIGGER;
  dst.kpm_ric_event_trigger_format_1.report_period_ms = period;
  return dst;
}

static
meas_info_format_1_lst_t gen_meas_info_format_1_lst(const char* action)
{
  meas_info_format_1_lst_t dst = {0};
  dst.meas_type.type = NAME_MEAS_TYPE;
  dst.meas_type.name = cp_str_to_ba(action);
  dst.label_info_lst_len = 1;
  dst.label_info_lst = calloc(1, sizeof(label_info_lst_t));
  assert(dst.label_info_lst != NULL && "Memory exhausted");
  dst.label_info_lst[0].noLabel = calloc(1, sizeof(enum_value_e));
  assert(dst.label_info_lst[0].noLabel != NULL && "Memory exhausted");
  *dst.label_info_lst[0].noLabel = TRUE_ENUM_VALUE;
  return dst;
}

static
kpm_act_def_format_1_t gen_act_def_frmt_1(const char** action)
{
  kpm_act_def_format_1_t dst = {0};
  dst.gran_period_ms = 100;
  size_t count = 0;
  while (action[count] != NULL) count++;
  dst.meas_info_lst_len = count;
  dst.meas_info_lst = calloc(count, sizeof(meas_info_format_1_lst_t));
  assert(dst.meas_info_lst != NULL && "Memory exhausted");
  for(size_t i = 0; i < dst.meas_info_lst_len; ++i)
    dst.meas_info_lst[i] = gen_meas_info_format_1_lst(action[i]);
  return dst;
}

static
kpm_act_def_t gen_act_def(const char** act)
{
  kpm_act_def_t dst = {0};
  dst.type = FORMAT_1_ACTION_DEFINITION;
  dst.frm_1 = gen_act_def_frmt_1(act);
  return dst;
}

static atomic_long g_ind_cnt = 0;
static void sm_cb_kpm(sm_ag_if_rd_t const* rd)
{
  (void)rd;
  atomic_fetch_add(&g_ind_cnt, 1);
}

volatile sig_atomic_t stop_flag = 0;
static void on_sigint(int sig){ (void)sig; stop_flag = 1; }

int main(int argc, char *argv[])
{
  const char* label = (argc > 1) ? argv[1] : "benign";

  fr_args_t args = init_fr_args(argc, argv);
  init_xapp_api(&args);
  sleep(1);

  e2_node_arr_t nodes = e2_nodes_xapp_api();
  defer({ free_e2_node_arr(&nodes); });
  assert(nodes.len > 0);

  // ColO-RAN kpimon 画像：KPM 100ms + TS 28.552 gNB 七项
  const int KPM_ran_function = 2;
  int n_sub_ok = 0;
  sm_ans_xapp_t* handles = calloc(nodes.len, sizeof(sm_ans_xapp_t));
  for (int i = 0; i < nodes.len; i++) {
    kpm_sub_data_t kpm_sub = {0};
    defer({ free_kpm_sub_data(&kpm_sub); });
    kpm_sub.ev_trg_def = gen_ev_trig(100);
    kpm_sub.sz_ad = 1;
    kpm_sub.ad = calloc(1, sizeof(kpm_act_def_t));
    assert(kpm_sub.ad != NULL);
    const char *act_gnb[] = {"DRB.PdcpSduVolumeDL", "DRB.PdcpSduVolumeUL", "DRB.RlcSduDelayDl",
                             "DRB.UEThpDl", "DRB.UEThpUl", "RRU.PrbTotDl", "RRU.PrbTotUl", NULL};
    *kpm_sub.ad = gen_act_def(act_gnb);
    handles[i] = report_sm_xapp_api(&nodes.n[i].id, KPM_ran_function, &kpm_sub, sm_cb_kpm);
    if (handles[i].success) n_sub_ok++;
  }
  printf("[benign:%s] subscribed OK %d/%zu nodes, holding (100ms period)\n",
         label, n_sub_ok, nodes.len);
  fflush(stdout);

  signal(SIGINT, on_sigint); signal(SIGTERM, on_sigint);

  int64_t t0 = time_now_us();
  long last_cnt = 0;
  while(stop_flag == 0){
    sleep(5);
    long c = atomic_load(&g_ind_cnt);
    printf("[benign:%s] t=%.0fs indications total=%ld (+%ld in 5s)\n",
           label, (time_now_us()-t0)/1e6, c, c - last_cnt);
    fflush(stdout);
    last_cnt = c;
  }
  printf("[benign:%s] SUMMARY indications_total=%ld elapsed=%.0fs\n",
         label, atomic_load(&g_ind_cnt), (time_now_us()-t0)/1e6);
  fflush(stdout);
  free(handles);
  while(try_stop_xapp_api() == false) usleep(1000);
  return 0;
}
