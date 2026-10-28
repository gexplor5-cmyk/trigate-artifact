/*
 * xapp_wcet.c — R1-D 标定负载器：N 笔 KPM 订阅（period 可配）长驻
 * 用法: xapp_wcet <n_subs> <period_ms>
 * 每笔订阅同参数（kpimon 画像），建满后长驻（agent 侧 [WCET] 打点采样）。
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

static atomic_long g_ind = 0;
static void sm_cb_kpm(sm_ag_if_rd_t const* rd){ (void)rd; atomic_fetch_add(&g_ind, 1); }

volatile sig_atomic_t stop_flag = 0;
static void on_sigint(int sig){ (void)sig; stop_flag = 1; }

int main(int argc, char *argv[])
{
  if(argc < 3){ fprintf(stderr, "usage: %s <n_subs> <period_ms>\n", argv[0]); return 1; }
  long n_subs = atol(argv[1]);
  long period_ms = atol(argv[2]);

  fr_args_t args = init_fr_args(argc, argv);
  init_xapp_api(&args);
  sleep(1);
  e2_node_arr_t nodes = e2_nodes_xapp_api();
  defer({ free_e2_node_arr(&nodes); });
  assert(nodes.len > 0);

  const int KPM = 2;
  long ok = 0;
  sm_ans_xapp_t* h = calloc(n_subs, sizeof(sm_ans_xapp_t));
  for(long k = 0; k < n_subs; ++k){
    kpm_sub_data_t kpm_sub = {0};
    defer({ free_kpm_sub_data(&kpm_sub); });
    kpm_sub.ev_trg_def = gen_ev_trig(period_ms);
    kpm_sub.sz_ad = 1;
    kpm_sub.ad = calloc(1, sizeof(kpm_act_def_t));
    assert(kpm_sub.ad != NULL);
    const char *act[] = {"DRB.RlcSduDelayDl", NULL};
    *kpm_sub.ad = gen_act_def(act);
    h[k] = report_sm_xapp_api(&nodes.n[k % nodes.len].id, KPM, &kpm_sub, sm_cb_kpm);
    if(h[k].success) ok++;
  }
  printf("[wcet] n=%ld period=%ldms subscribed_ok=%ld holding\n", n_subs, period_ms, ok);
  fflush(stdout);
  signal(SIGINT, on_sigint); signal(SIGTERM, on_sigint);
  int64_t t0 = time_now_us();
  while(stop_flag == 0){
    sleep(5);
    printf("[wcet] t=%.0fs ind=%ld rate=%.1f/s\n", (time_now_us()-t0)/1e6,
           atomic_load(&g_ind), atomic_load(&g_ind)/((time_now_us()-t0)/1e6));
    fflush(stdout);
  }
  printf("[wcet] SUMMARY n=%ld period=%ld ind=%ld\n", n_subs, period_ms, atomic_load(&g_ind));
  fflush(stdout);
  free(h);
  while(try_stop_xapp_api() == false) usleep(1000);
  return 0;
}
