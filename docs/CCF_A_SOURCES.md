# 图学习相关 CCF-A 会议来源核验

核验日期：2026-09-27。范围是适合查找图学习论文的会议，不代表各会议所有论文都属于图学习。分类依据为 CCF 官方的[人工智能](https://www.ccf.org.cn/Academic_Evaluation/AI/)、[数据库/数据挖掘](https://www.ccf.org.cn/Academic_Evaluation/DM_CS/)、[交叉/综合/新兴](https://www.ccf.org.cn/Academic_Evaluation/Cross_Compre_Emerg/)和[图形学与多媒体](https://www.ccf.org.cn/Academic_Evaluation/CGAndMT/)目录。`docs/conference_sources.json` 保存逐年入口，`scripts/probe_conference_sources.py` 只读探测这些入口，`docs/conference_source_audit.json` 保存本次 HTTP、样例详情与 PDF 核验记录。

状态说明：**可接入**指目录和论文详情或 PDF 已实际读通；**部分**指能看到目录/标题但缺少稳定的详情、摘要或 PDF；**待接入**指本次未找到可稳定解析的论文目录。状态只说明本机本次访问结果，不保证日后站点不变。探针只抽样，不代表已逐篇核验主会身份或图学习相关性。

| CCF-A 会议 | 2025 | 2026 | 优先论文入口与核验结论 |
| --- | --- | --- | --- |
| ICML | 可接入 | 可接入 | [2025](https://icml.cc/virtual/2025/papers.html) / [2026](https://icml.cc/virtual/2026/papers.html) 的论文目录和 poster 摘要可读；2025 样例详情可读，2026 样例为图持续学习。详情页的幻灯片 PDF 不能当论文 PDF；论文正文需另核 OpenReview/PMLR。 |
| NeurIPS | 可接入 | 待接入 | [2025 论文集](https://proceedings.neurips.cc/paper_files/paper/2025) 有摘要和 PDF；抽样碰到 Creative AI Track，正式采集须过滤 track。[2026 论文集](https://proceedings.neurips.cc/paper_files/paper/2026) 本次 404，virtual 页 403。 |
| AAAI | 可接入 | 可接入 | [2025 Technical Tracks 样例目录](https://ojs.aaai.org/index.php/AAAI/issue/view/637) / [2026](https://ojs.aaai.org/index.php/AAAI/issue/view/703)：article 页有摘要、DOI、精确日期和论文 PDF。完整采集须从 [archive](https://ojs.aaai.org/index.php/AAAI/issue/archive) 遍历全部 Technical Tracks 卷，不只抓一个 issue。 |
| IJCAI | 可接入 | 可接入 | [2025](https://www.ijcai.org/proceedings/2025/) / [2026](https://www.ijcai.org/proceedings/2026/) 的目录、详情、PDF 可读；详情有会议名及日精度发表日期。 |
| KDD (SIGKDD) | 待接入 | 部分 | [2025 官网](https://kdd2025.kdd.org/) 的已知 research-track 路径本次 404；[2026 papers](https://kdd2026.kdd.org/papers/) 可访问，但本次没有解析出论文级链接。需进一步找正式 proceedings/OpenReview，并筛选 Research Track。 |
| WWW | 待接入 | 部分 | [2026 官网](https://www2026.thewebconf.org/) 指向 [主会 ACM 论文集](https://dl.acm.org/doi/proceedings/10.1145/3774904)，但 ACM 本机 403。Companion 论文集 DOI `10.1145/3774905` 必须排除；2025 官网本机连接失败。 |
| SIGIR | 部分 | 待接入 | [2025 proceedings](https://sigir2025.dei.unipd.it/proceedings.html) 有论文标题及 ACM DOI，抽到图推荐论文，但 ACM 详情本机未读通；[2026 官网](https://sigir2026.org/) 本次未解析到论文清单。需区分 full/short、workshop。 |
| ACL | 可接入 | 可接入 | [2025](https://aclanthology.org/events/acl-2025/) / [2026](https://aclanthology.org/events/acl-2026/) 的 Anthology 可读详情、摘要和 PDF。只取 `acl-long` 主会；网页 citation 日期只有年月，精确日期需另外核验，不能补造日。 |
| CVPR | 可接入 | 可接入 | [2025](https://openaccess.thecvf.com/CVPR2025?day=all) / [2026](https://openaccess.thecvf.com/CVPR2026?day=all) 的开放论文目录、摘要和 PDF 可读；citation 日期只给年份。 |
| ICCV | 可接入 | 不适用 | [2025 开放论文集](https://openaccess.thecvf.com/ICCV2025?day=all) 可读详情、摘要和 PDF。ICCV 为奇数年双年会议，2026 没有常规届。 |
| SIGMOD | 部分 | 部分 | [2025 accepted papers](https://2025.sigmod.org/sigmod_papers.shtml) / [2026](https://2026.sigmod.org/sigmod_papers.shtml) 有标题；PACMMOD 承载论文，不能将任意 PACMMOD 期刊文章直接当 SIGMOD 主会。ACM DOI 详情本机不稳定。 |
| VLDB | 部分 | 部分 | [PVLDB 18](https://www.vldb.org/pvldb/volumes/18/) / [PVLDB 19](https://www.vldb.org/pvldb/volumes/19/) 目录可读；19 卷横跨 2025–2026，不能仅凭卷号断言会议年份。需解析论文条目并验证 VLDB 届次、摘要、PDF。 |
| ICDE | 待接入 | 待接入 | [IEEE Xplore proceedings](https://ieeexplore.ieee.org/xpl/conhome/1000178/all-proceedings) 本机返回安全脚本页面，HTTP 200 不等于论文可读；需找当年官网论文清单或可用的开放元数据入口。 |
| ACM MM | 部分 | 待接入 | [2025 accepted regular papers](https://acmmm2025.org/accepted-regular-papers/) 可读目录；[2026 官网](https://2026.acmmm.org/) 本次未解析出论文清单。accepted 列表不等于正式发表的详情和 PDF。 |

**推荐接入顺序。** 第一批接 ICML、AAAI、IJCAI、ACL、CVPR、ICCV 2025、NeurIPS 2025，按论文详情核对标题、摘要、正式 venue/track、可用 PDF 和发表日期。第二批针对 KDD、WWW、SIGIR、SIGMOD、VLDB、ICDE、ACM MM 单独写站点适配器或接官方开放元数据；仅有标题/首页时不要生成缺证据的摘要。已存在 arXiv 记录须按 DOI、OpenReview ID、规范化标题等合并，不要因为会议页与预印本链接不同就重复展示。ICLR 未出现在本次核对的 CCF-A 人工智能目录，不应标成 A 类；EMNLP 是用户指定的 B 类例外，保持现有产品规则。

**日期限制。** 会议届次年份不是发表日期。NeurIPS 2025 样例页曾出现 `citation_publication_date=2026-08-14`；ACL 和 CVF 页面分别可能只有年月、年份。现有短期日期窗口必须只接受有可靠日精度日期的论文，或单独设计带日期精度标记的策略，不能用会议举行日填充每篇论文的发表日。

重跑只读探测：`python -X utf8 scripts/probe_conference_sources.py`。探测不会调用 LLM，也不会修改正式论文归档；该脚本目前是来源审计工具，不是正式采集适配器。
