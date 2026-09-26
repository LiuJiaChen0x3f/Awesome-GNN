# 同类项目调研与实现决策

调研日期：2026-09-26。以下来自项目 README、GitHub repository metadata、原始源码和官方文档；不采用未经核验的星标数或“最佳项目”排名。

| 项目 | 匹配情况 | 本项目决策 |
| --- | --- | --- |
| [yang3kc/daily_arxiv_digest](https://github.com/yang3kc/daily_arxiv_digest) | 无人值守LLM论文摘要流水线、可独立运行的arXiv采集skill、MIT；skill仅用标准库 | 复用RSS解析脚本，固定提交并保留MIT；不用其完整依赖栈，因为还需跨来源身份合并、强制5词/100字和特定筛选UI |
| [DaizeDong/Daily-ArXiv-Assistant](https://github.com/DaizeDong/Daily-ArXiv-Assistant) | arXiv与AI热点聚合、静态站点、Apache-2.0 | 作为流程参考；用户会提供自己的API，故不引入它的模型与运行方式 |
| [dw-dengwei/daily-arXiv-ai-enhanced](https://github.com/dw-dengwei/daily-arXiv-ai-enhanced) | 自动论文采集、AI摘要、GitHub Pages | 作为方案参考；GitHub license metadata返回NOASSERTION，不在本轮复制其实现 |

结论：已有接近的项目，没必要从零发明RSS解析；但直接套用完整站点不能免去多来源去重、百字约束和持久增量处理。因此使用“实际复用一个独立模块 + 为需求补齐轻量应用”的方案。前端原生静态实现，无打包依赖。

## 实际复用范围

- 原文件：`skills/arxiv-fetch/scripts/fetch_arxiv.py`
- 上游提交：`9d19de2534fa9d89c3904128891779a2d32056d8`
- 本地：`gnn_digest/vendor/arxiv_rss.py`，下载时未修改。
- 调用：`_clean_abstract`、`_extract_arxiv_id`、`_parse_authors`，用于RSS回退。
- 原许可证：`gnn_digest/vendor/daily_arxiv_digest.LICENSE`。
- 固定来源：`gnn_digest/vendor/PROVENANCE.json`。

## 官方资料

- [arXiv API user manual](https://info.arxiv.org/help/api/user-manual.html)：Atom字段、排序与分页。按小页串行获取，页间留间隔；故障时RSS回退。
- [arXiv API usage](https://info.arxiv.org/help/api/tou.html)：访问规范。
- [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) 与 [API源码文档](https://github.com/CrossRef/rest-api-doc)：日期过滤、查询参数、摘要可能缺失。
- [OpenAlex API reference](https://help.openalex.org/api/) 与 [Authentication](https://help.openalex.org/api/authentication/)：使用Bearer认证；本项目启用此来源时要求提供API key。原摘要倒排索引重建为连续文本。
- [GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)：构建、上传artifact、部署Pages及权限。
- [GitHub Actions events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)：定时任务语义。

## 本轮验证边界

arXiv和Crossref已进行真实联网抓取。OpenAlex适配器尚无用户key，未声称完成认证调用。模型的结构校验、错误重试、缓存及本地HTTP协议可测试，但供应商模型质量和实际接口兼容性需拿到用户配置后验证。页面可在本地预览，远程仓库和Pages部署需用户仓库地址。
