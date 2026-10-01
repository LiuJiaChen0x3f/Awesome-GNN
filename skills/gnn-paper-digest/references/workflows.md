# 操作参考

本文件只供 `gnn-paper-digest` Skill 在相关任务中按需读取；命令均从 Awesome-GNN 仓库根目录执行。

## 批量检索与窗口

`python -X utf8 run.py search --limit 100` 启用 `gnn_digest/bulk.py`。默认会议从 2025-01-01 起、arXiv v1 从启动时 UTC 日往前两个自然月起，截止启动时的 UTC 日；会议再限定 2025/2026 届，跳过不存在常规届的 ICCV 2026。可用 `--conference-since`、`--arxiv-since` 或 `--conference-days`、`--arxiv-days` 临时改窗口。原站只有年/月时保留精度，不补造日。大批次默认最多两轮会议覆盖、四批 arXiv、7200 秒软预算和 240 次全文处理；预算耗尽应保存已有结果并列出缺口。

批量检查点保存在 `data/bulk_run.json`，逐批同步 `data/papers.json` 和站点索引。中断后先确认原进程已经退出；仅在目标、窗口及检查点身份一致时执行 `python -X utf8 run.py search --limit 100 --resume`。不要在运行进程仍持有锁时删除 `data/pipeline.lock`。

小批次默认由 `config.json.search_agent` 控制轮数、时长及总结预算。DeepSeek 兼容路径使用本地 scholarly 工具；Responses 供应商可能不支持 `max_tool_calls`，不能把提示词里的工具次数目标说成硬性限制。超时或网络故障不要无界重试付费请求。

## 来源、全文与总结

允许会议及别名在 `gnn_digest/verification.py`，还须与配置同步。arXiv 不区分会议等级；非 arXiv 需要出版方或正式论文集的主会证据。会议目录可以初筛题名，不能单独证明录用或发表日期。KDD、WWW、SIGIR、SIGMOD、VLDB、ICDE、ACM MM 等目录中的候选可按精确题名寻找 arXiv 全文；独立核对题名后，arXiv 只提供正文，不改变会议身份或名额。OpenReview 投稿页本身不证明录用。SIGMOD/PVLDB 期刊式论文还须核对对应年会议名单。

正文由 `gnn_digest/fulltext.py` 提取，搜索总结模型读取覆盖全文的编号片段。模型给出证据编号；`gnn_digest/evidence.py` 从实际正文恢复连续片段与偏移，虚构编号拒绝。`gnn_digest/summary_policy.py` 校验总结长度、加粗和关键词。缺全文、缺主会身份、日期不明、主题只有背景提及、供应商失败分别保留状态，不伪造完成。`data/last_run.json` 的 `stage`、`code`、`next_action`、配额及工具动作可定位失败。

## 独立补漏审计

2026-09-30 用户确认：正式归档的专题研究/数据集轨道可纳入，包括 IJCAI 的 AI and Social Good、AI and Health、AI4Tech，以及 NeurIPS Datasets and Benchmarks。仍排除 Findings、workshop、演示、博士生论坛、综述；基准论文也须有实际 TAG/OOD 方法。官方轨道保存在论文 `publication_track` 和 `verification.track` 中，不把投稿页或相似题名当录用证据。

最新会议届次补漏使用 `scripts/audit_literature.py` 等项目脚本，范围与待处理项见 `docs/latest_conference_coverage_audit.md`、`data/literature_pending.json`。这条审计路径扩展了 ICLR、LoG、ICDM、WSDM、NAACL 等来源，不能说普通 `run.py search` 自动覆盖了全部审计范围。审计缓存位于 gitignored `.local/literature-audit/`，远端仓库不包含它；恢复脚本也不会自动重新抓取所有待处理候选。最新届次未能访问时不推断其未公布。

已有结果的收尾命令：

```powershell
python -X utf8 scripts/publish_literature_audit.py --final
python -X utf8 scripts/report_literature_audit.py
python -X utf8 scripts/validate_literature_export.py
```

只有确定缓存与审计范围一致时才执行发布，不把候选数当作已核验论文数。

## 兼容入口与发布

旧 `python run.py run`、`python run.py summarize`、`python run.py build` 分别是旧来源采集、补总结、重新导出；不等于新 `search` 的完整联网核验。`run --no-llm` 只采集真实元数据，不生成猜测总结。更改总结提示词会使相关缓存失效。

页面仅读取 `site/data/papers.json`。本机预览：`python -m http.server 8000 --directory site`。用户要求上线时先核对索引和敏感信息，再同时提交需要的 `data/`、`site/` 文件并推送到指定仓库；`site/**` 改动触发 `.github/workflows/pages.yml`。最后查看 Actions 结果和线上页面、索引，不能只把本地浏览器成功当作已发布。

## 验证

```powershell
python -m unittest discover -s tests -v
node --check site/app.js
python -X utf8 scripts/validate_literature_export.py
```

按改动范围选择检查；涉及页面还核对桌面/手机布局、筛选、空状态及 PDF 链接。涉及新检索逻辑时依用户约定真实检索 3 篇并报告会议/arXiv 配额与不足；用户要求只修改不运行时遵从本次要求。
