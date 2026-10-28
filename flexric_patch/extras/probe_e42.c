/* probe_e42.c — 最小 E42 探针：connect→发 setup 模板→循环 recv 打印一切 */
#include "e42_templates.h"
#include <arpa/inet.h>
#include <netinet/in.h>
#include <netinet/sctp.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>

int main(void)
{
  signal(SIGPIPE, SIG_IGN);
  int fd = socket(AF_INET, SOCK_SEQPACKET, IPPROTO_SCTP);
  struct sockaddr_in sa = {0};
  sa.sin_family = AF_INET; sa.sin_port = htons(36422);
  inet_pton(AF_INET, "127.0.0.1", &sa.sin_addr);
  if(connect(fd, (struct sockaddr*)&sa, sizeof(sa)) == -1){ perror("connect"); return 1; }
  printf("connected\n");
  struct sctp_event_subscribe ev = {0};
  ev.sctp_data_io_event = 1;
  setsockopt(fd, IPPROTO_SCTP, SCTP_EVENTS, &ev, sizeof(ev));
  int nd=1; setsockopt(fd, IPPROTO_SCTP, SCTP_NODELAY, &nd, sizeof(nd));

  int rc = sctp_sendmsg(fd, TPL_SETUP_REQ, TPL_SETUP_REQ_len, NULL, 0, 0, 0, 0, 0, 0);
  printf("setup send rc=%d errno=%s\n", rc, rc==-1?strerror(errno):"-");

  unsigned char buf[65536];
  struct sctp_sndrcvinfo sri; int flags=0;
  struct sockaddr_in from; socklen_t flen=sizeof(from);
  for(int i=0;i<5;i++){
    flags=0;
    ssize_t n = sctp_recvmsg(fd, buf, sizeof(buf), (struct sockaddr*)&from, &flen, &sri, &flags);
    if(n<0){ printf("recv[%d] = %zd errno=%s\n", i, n, strerror(errno)); continue; }
    printf("recv[%d] = %zd flags=%#x notif=%d stream=%u ppid=%u first16=%s\n",
           i, n, flags, !!(flags & MSG_NOTIFICATION), sri.sinfo_stream, sri.sinfo_ppid,
           n>0 ? "" : "");
    for(int k=0;k<(n<16?n:16);k++) printf("%02x", buf[k]);
    printf("\n");
    if(!(flags & MSG_NOTIFICATION)) break;  // DATA 到达即停
  }
  return 0;
}
