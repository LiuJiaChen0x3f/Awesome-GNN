# ICML / ICLR 官网检索实测

测试日期：2026-09-27（Asia/Shanghai）。本轮仅验证来源能力，未调整准入、时间窗口、配额或论文归档。

## 结果

本机使用普通公开HTTPS请求读取以下页面，均返回HTTP 200：

- https://icml.cc/virtual/2026/papers.html
- https://iclr.cc/virtual/2026/papers.html
- https://icml.cc/virtual/2026/poster/66365 — GFFMERGE: Efficient Merging of Graph Neural Force Fields and Beyond
- https://iclr.cc/virtual/2026/poster/10006675 — Improving Long-Range Interactions in Graph Neural Simulators via Hamiltonian Dynamics
- https://proceedings.iclr.cc/paper_files/paper/2026/hash/0a5be8b9369d58c8ff7eb93caff06fff-Abstract-Conference.html — Efficient Learning on Large Graphs using a Densifying Regularity Lemma

两个官网poster页均在HTML正文提供完整摘要及OpenReview链接，但没有当前通用解析器要求的citation元数据。ICLR proceedings样例提供citation_title、citation_publication_date=2026-04-20和citation_pdf_url；其摘要与会议标识仍需要针对页面结构解析。解析器abstract_chars=0不代表网站没有摘要。

官网poster页显示的2026-07-08（ICML样例）和2026-04-24（ICLR样例）是展示日，不能当作首次发表日期。

## 现有模型接口实测

使用本机既有配置发出两次Responses请求，无摘要生成、不写入真实论文数据：

1. 4.94秒返回completed，但没有web_search动作，反而询问会议名称；请求细节仅放在instructions时未可靠执行。不算搜索成功。
2. 把完整任务同时放入input后，45.55秒完成8个web_search动作（search/open_page），返回ICML、ICLR官方论文链接。ICML具体打开记录为2025样例；ICLR记录有论文集引用，工具轨迹没有单独的ICLR open_page记录，因此不能仅凭回答宣称两站均被模型成功打开。另行本机HTTP核验已证明2026具体页面可读。

结论：网站可以作为搜索和读取来源；模型单次搜索的召回与工具执行仍需核验，不能保证每次找到最新年份。PDF元数据链接可获得，本轮未独立下载验证PDF内容。

## 当前项目接入障碍

- `gnn_digest/verification.py` 的DOMAINS没有icml.cc、iclr.cc、openreview.net；当前会在核验前拒绝这些域名（iclr.cc子域名同样被拒）。
- VENUES已含ICML，但未含ICLR。搜索可达性和会议准入是两件事；要将ICLR计入会议配额，需明确将它纳入项目允许会议，不能自行标作CCF-A。
- 只增加域名不够：官网详情页须提取标题/作者/摘要/主会身份，再跟随正式论文集或OpenReview核对出版信息及PDF。不能把投稿、录用、修订或海报展示日期替代发表日。
- 最近14天窗口仍会排除更早出版的会议论文。增加来源不能保证补齐窗口内会议配额。

建议的接入链路：ICML官网发现 → PMLR/OpenReview核验；ICLR官网发现 → proceedings.iclr.cc/OpenReview核验。继续由LLM自主搜索，不恢复固定关键词爬取；保留跨源去重和会议/arXiv各半配额。

本机脱敏探测记录在gitignored的`.local/conference_sites_report.json`、`.local/conference_sites_first_report.json`和`.local/conference_details_report.json`；可复跑脚本同目录。API key未写入脚本和报告。
