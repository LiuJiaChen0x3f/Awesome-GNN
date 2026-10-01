# TAG / OOD 最新会议论文覆盖审计

核查基准日：2026-09-29；恢复复核日：2026-10-01。报告生成：2026-10-01T04:43:02.685033+00:00。

本轮去重后新增 **288 篇**，本地公开索引合计 **401 篇**。
这是有来源证据的补漏结果，不是“已收齐全部相关论文”的声明。未获得全文、名单访问失败和审核失败均保留为待处理项。

## 范围和取舍

- 每个会议独立选择最新公开可核验届次：有 2026 就用 2026，否则核查 2025。访问失败不能证明 2026 尚未公布。
- 保留原有 113 篇公开记录；本轮新增执行最新届次规则，没有擅自删除之前收录的旧届论文。
- 范围扩展至 ICLR、LoG、ICDM、WSDM、NAACL。纳入正式归档的专题研究及数据集/基准轨道，包括 IJCAI AI and Health / AI and Social Good / AI4Tech、NeurIPS Datasets and Benchmarks；仍排除 Findings、workshop、演示、博士生论坛、综述及尚未核验的投稿。
- TAG/OOD 必须是论文实际方法或实验设置。仅背景提及、普通归纳划分、训练客户端 Non-IID 不足以认定 OOD。
- 每篇卡片有完整正文输入、151–200 可见字符方法总结、1–4 处方法加粗、1–5 个内部关键词和可定位全文证据；网页只展示 TAG/OOD 主题。

## 各会议结果

“页面该届”是该届目前已上架的论文总数，包含此前已收录记录；“待处理”是尚未完成核验的候选论文数，不是等待举办的会议，也不是已确认相关论文数。
恢复处理结果及范围选择见 [待处理清单处理记录](pending_resolution.md)。已确认的非主会轨道不再混入技术失败清单。

2026-10-01 全文补查与严格主题复核见 [arXiv 与出版方补查记录](arxiv_recovery_2026-10-01.md)。

| 会议 | 本轮届次 | 新增 | 页面该届 | 待处理 | 届次证据状态 |
|---|---:|---:|---:|---:|---|
| AAAI | 2026 | 48 | 68 | 0 | 已核验该届论文来源 |
| ACL | 2026 | 22 | 25 | 3 | 已核验该届论文来源 |
| ACM MM | 2025 | 1 | 2 | 16 | 2025 暂作回退，2026 仍待确认 |
| CVPR | 2026 | 12 | 15 | 0 | 已核验该届论文来源 |
| EMNLP | 2026 | 24 | 26 | 37 | 已核验该届论文来源 |
| ICCV | 2025 | 5 | 7 | 0 | 已核验该届论文来源 |
| ICDE | 2026 | 1 | 1 | 5 | 已核验该届论文来源 |
| ICDM | 2025 | 1 | 1 | 14 | 2025 暂作回退，2026 仍待确认 |
| ICLR | 2026 | 43 | 43 | 2 | 已核验该届论文来源 |
| ICML | 2026 | 36 | 40 | 0 | 已核验该届论文来源 |
| IJCAI | 2026 | 12 | 24 | 0 | 已核验该届论文来源 |
| KDD | 2026 | 13 | 19 | 28 | 已核验该届论文来源 |
| LoG | 待确认 | 0 | 0 | 0 | 最新名单待核验 |
| NAACL | 2025 | 8 | 8 | 0 | 已核验该届论文来源 |
| NeurIPS | 2025 | 48 | 51 | 0 | 2025 暂作回退，2026 仍待确认 |
| SIGIR | 2026 | 1 | 2 | 11 | 已核验该届论文来源 |
| SIGMOD | 2026 | 0 | 0 | 4 | 已核验该届论文来源 |
| VLDB | 2026 | 4 | 5 | 1 | 已核验该届论文来源 |
| WSDM | 2026 | 2 | 2 | 3 | 已核验该届论文来源 |
| WWW | 2026 | 7 | 10 | 42 | 已核验该届论文来源 |

## 发现与筛选覆盖

- 参考仓库完整 Git tree 未截断；读取了 25 个 2025/2026 索引，共 3,598 条目录记录。结合官网、出版方元数据形成独立候选集。
- 合并候选集 3440 条，其中符合最终届次的 3274 条；按真实候选 ID 统计成功初筛 3214 条，另有 60 条已在原库，无成功初筛且不在原库的 0 条。
- 初筛是高召回候选选择，不是全文排除证明；题名未明显表达 TAG/OOD 的论文仍可能漏检。
- EMNLP 2026 独立处理：官方公开日程含 2,710 个 MAIN 条目，提取并核验 85 个图相关题名；该计数不混入前面的历史索引 ID。
- 修正了额外初筛缓存的批次编号漂移：覆盖率按成功 reviewed_ids 的并集计算；补审缓存以输入内容哈希命名，不再通过批次数推断覆盖率。

## 仍然存在的缺口

- LoG 2026 官方征稿页列出的决定公布日期为 9 月 13 日，但本次官网 Program 仍为占位链接，OpenReview 录用名单/轨道尚未完整核验。决定日期不等于已取得公开名单，不将 LoG 2025 冒充已确认的最新届次。
- NeurIPS 2026 目录返回 403，正文明确提示会议虚拟站点尚未开放；2025 作为可核验回退。ACM MM 2026 首页可达但未取得完整论文目录，ICDM 站点存在 TLS 访问失败，不能据此断言论文未公布。
- EMNLP 2026 多数题名尚未定位到可核对的完整正文；两篇原有 arXiv 记录已根据官方 MAIN 名单补充会议归属，不重复新增。
- ECCV 2026 未在参考仓库快照中发现相应索引，官网请求发生 SSL 错误；记录为范围缺口，不宣称已覆盖。
- 出版方/OpenReview PDF 返回访问错误、无可匹配全文，以及超出 PDF 安全大小限制的候选仍未上架；不能使用相似题名替代。
- 最新届次待处理：书目 28 条，全文 138 条，模型请求失败 0 条，总结校验失败 0 条，已取全文待总结 0 条，主题证据待复核 0 条。数量是候选记录数；请求成功不代表所有站点持续可达。

## 可复核文件与恢复

- `data/literature_audit_scope.json`：有效届次和证据限制。
- `data/literature_audit_results.json`：新增论文题名、会议、总结和 PDF。
- `data/literature_coverage_check.json`：实际成功审核 ID 的覆盖核算。
- `data/literature_pending.json`：所有未解决候选、错误及原站线索。
- `.local/literature-audit/`：本机全文缓存、失败历史、修订前记录；不进入公开网页。

```powershell
# 只恢复已有全文的总结，连续请求失败会停止；会调用本机配置的 API
python -X utf8 scripts/summarize_literature_candidates.py --retry-failed --limit 150
# 仅核验并导出已完成结果，不调用模型
python -X utf8 scripts/publish_literature_audit.py --final
python -X utf8 scripts/report_literature_audit.py
```

本轮更新在本地；未提交或推送 GitHub。最终结果须以最后一次导出后的数字为准。

## 主要来源

- https://github.com/naganandy/graph-based-deep-learning-literature/tree/master
- ACL: https://aclanthology.org/events/acl-2026/
- ICCV: https://openaccess.thecvf.com/ICCV2025
- NAACL: https://aclanthology.org/events/naacl-2025/
- NeurIPS: https://proceedings.neurips.cc/
- CVPR: https://openaccess.thecvf.com/CVPR2026
- LoG: https://openreview.net/group?id=logconference.io/LOG/2026/Conference
- ICLR: https://proceedings.iclr.cc/paper_files/paper/2026
- EMNLP: https://2026.emnlp.org/program/
- AAAI: https://ojs.aaai.org/index.php/AAAI/issue/archive
- IJCAI: https://www.ijcai.org/proceedings/2026/
- ICML: https://icml.cc/virtual/2026/papers.html
- SIGMOD: https://2026.sigmod.org/sigmod_papers.shtml
- VLDB: https://www.vldb.org/2026/program.html
