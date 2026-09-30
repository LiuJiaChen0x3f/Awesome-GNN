# Awesome GNN · 图学习研究雷达

## 推荐入口：本地联网搜索代理

```powershell
cd D:\Awesome-GNN
# 修改固定研究需求，不必填写检索词
notepad prompts/search.request.txt
python -X utf8 run.py search --limit 100
# 默认会议覆盖2025/2026届，arXiv从2026-01-01起；临时覆盖窗口
python run.py search --limit 3 --conference-days 90 --arxiv-days 14
# 兼容参数：同时将两类窗口改为30天
python run.py search --limit 3 --days 30
```

本机 `.env` 使用 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL / LLM_REASONING_EFFORT。`search` 让模型动态决定检索查询：DeepSeek 使用 Chat Completions 自定义 `web_search` 函数，由本地程序访问 arXiv/Crossref；支持原生 Responses 联网工具的供应商则走 Responses 路径。每轮返回候选后，程序独立核验标题、日期、会议，反馈拒绝原因和缺口。随后读取可获取的论文全文，通过 Chat Completions 生成1至5个内部方法关键词、151至200个可见字符的方法总结及有全文证据的TAG/OOD主题。没有合格结果不会凑数。

收录：项目列出的CCF-A主会 + EMNLP主会，或独立核验的arXiv论文（不限会议等级）。主题仅限**TAG（文本属性图）或OOD（图学习分布外泛化）**，命中一个即可，也可同时命中；须由全文支持主要方法或任务，不以背景提及、泛泛的鲁棒性或普通少样本任务强行贴标签。arXiv用v1首次提交日，会议用正式发表日；不以修订日期冒充新论文。来源日期不足以证明窗口归属或缺会议元数据时拒绝并反馈，不根据模型声称的事实放行。主站域名和会议别名在 `gnn_digest/verification.py`，它不是完整CCF-A目录。

输出：`data/search_results.json` 保存本次合格论文；`data/last_run.json` 保存每轮工具动作、引用、拒绝原因、用量与停止原因；`data/papers.json` 持久去重归档，`site/data/papers.json` 是网页数据。网页默认最新优先、来源标签使用简称/arXiv、链接PDF优先；历史归档仍在，旧记录不声称已经新规则复核。

`--limit` 是1至100篇的目标数量（超过20自动启用会议/年份批量遍历），覆盖需求文件内的示例数量。退出码0达到目标，4表示有搜索但不足，2表示联网搜索未成功。搜索排序是预算内的最佳努力，不能宣称全网最新排名。源码、测试和归档均不含密钥。

**100篇批量入口**：`python -X utf8 run.py search --limit 100`先找最多20篇2026年初以来的arXiv论文，再逐项搜索所有启用会议的2026、2025届已公布论文。初始目标80会议+20arXiv；arXiv不足部分回补会议，0篇arXiv时目标100会议。每篇跨来源只计一次。先完成全部适用会议/年份的一轮搜索（即使中途达到数量，也完成剩余会议的发现检查），不足再进行一次补搜；仍不足则保存部分结果并停止。不声称搜索无结果就代表该会议没有相关论文。1至20篇的兼容小批次仍使用原来的会议/arXiv各半比例。

批量覆盖：NeurIPS、ICML、KDD、AAAI、IJCAI、ACL、CVPR、ICCV、SIGMOD、VLDB、SIGIR、WWW、ICDE、EMNLP、ACM MM。不检索没有常规届次的ICCV 2026。未公布、访问失败、原站证据不足等情况保留在每个批次记录；不以其他会议替代该会议的检索。ICLR不因本次扩展自动纳入项目CCF-A白名单。

`data/bulk_run.json`保存整体进度、原始/调整后配额和会议年份覆盖；`data/last_run.json`、`data/search_results.json`及静态索引在每批完成后同步。排他锁覆盖整个批量任务，中断前已核验论文逐篇保存在归档。默认每批最多12篇、arXiv最多4批、会议最多2遍、总软时间预算7200秒/240篇全文处理；预算不足与全覆盖结束分别报告。

`config.json.search_agent` 默认3轮、单请求超时180秒、总软预算600秒、每轮10候选、10篇全文总结预算（目标更大时至少为目标数）。DeepSeek 使用每轮最多4次本地函数工具调用，超时不会自动重发付费搜索。Responses 供应商若拒绝可选 `max_tool_calls` 参数，默认 `send_max_tool_calls=false`；外层限制轮数、输出token和时间。

提示词：`search.request.txt` 是用户需求，`search.agent.txt` 是搜索执行与JSON格式，`search.summary.zh.txt` 是全文总结规则。DeepSeek 路径需要支持 Chat Completions 函数调用；其他供应商可支持 Responses 联网工具；总结统一使用 Chat Completions。

时间窗口：`config.json.search_windows.conference_since=2025-01-01`、`arxiv_since=2026-01-01`，截至运行当日；批量会议另外限制2025、2026届。支持`--conference-since`、`--arxiv-since`及旧的`--conference-days`/`--arxiv-days`/`--days`覆盖。`source_windows`记录实际范围。原站只有年/月时保留真实精度，只在能证明属于宽窗口时接受，不补造日期；ICML官方节目页使用自身结构化题名、ICML届次及datePublished核验；不将活动日期或OpenReview创建日期冒充发表日。

多步补搜：反馈包含 `stage`、`code`、`next_action`，区分缺日期、缺会议身份、标题不符、访问失败和缺全文；模型据此打开原站或精确标题补搜。标题纠正/临时网络失败可按`retry_same_url`再核验一次，其余拒绝不重复。Responses路径的`open_page`是供应商工具，本机浏览器并未自动接入独立Python命令；网页可被模型打开也不绕过本机独立核验。

全文总结：`search`将全部提取正文连续分段并加编号（每段最多180字符，未截断全文），让模型综合全文输出方法并选择`evidence_ids`、`topic_evidence_ids`。程序从原文取回证据，保存实际片段和字符偏移；虚构编号被拒绝。兼容旧的逐字引文输出，只容忍空白排版差异。数量、类型、长度、不在原文等失败分别诊断，最多按现有预算修复一次。归档记录证据及修复过程，网页不输出全文或证据。

方法总结严格**151–200个可见Unicode字符**，去掉Markdown加粗标记及全部空白后计数（中文、标点、英文字符、数字各计一个），推荐生成170–190字符。按“具体问题→输入/表示→关键模块与信息流→学习目标/下游推理”写3至4句，突出TAG的文本结构融合或OOD的分布变化应对机制；不足时补原文细节，不能用空话或虚构结论凑长度。用`**方法名**`加粗1至4个关键方法、模块或目标。页面只解释加粗与换行，不执行HTML、链接或代码。字数、加粗和主题由程序校验，错误按预算修复；修改提示词后旧总结缓存失效。

网页主题筛选及卡片标签仅显示TAG/OOD，内部1至5个方法关键词仍参与搜索。不符合两类主题的旧记录不展示，也不会自动重新贴标签。修改`site/app.js`、`site/method-markdown.js`或CSS时，同步更新`index.html`中的内容哈希版本，避免浏览器混用新旧资源。

只保留测试和静态Pages发布工作流，**没有每日采集任务，无需远程保存模型密钥**。本机运行后按需提交并推送网页数据。以下旧 `run` / `summarize` 命令作为兼容入口保留，不具有新 `search` 的完整核验流程。

自动查找近期 TAG/OOD 论文，用**主题标签 + 151至200个可见字符的中文核心方法**帮读者快速筛选。本地手动发起后自动完成搜索、核验、去重和总结。

后端 Python 3.11+，PDF 解析依赖 `pypdf`；前端 HTML/CSS/JavaScript，无需 Node 构建，部署到 GitHub Pages。

> 当前本机联调配置为 Yundou 的 `gpt-5.6-sol`、`low` 推理强度。密钥仅从环境变量或本机 `.env` 读取，不随仓库发布。数据状态与覆盖范围见页面及 `data/last_run.json`。

## 兼容入口：旧批处理

在仓库根目录运行：

```powershell
# 安装 PDF 解析依赖，再抓取真实数据
python -m pip install -e .
python run.py run --no-llm

# 预览页面，然后浏览器打开 http://localhost:8000
python -m http.server 8000 --directory site
```

复制 `.env.example` 为 `.env`，填写你自己的兼容 Chat Completions 的服务：

```dotenv
LLM_BASE_URL=https://your-provider.example/v1
LLM_API_KEY=你的密钥
LLM_MODEL=你的模型名
LLM_REASONING_EFFORT=low
```

`LLM_BASE_URL` 既可填 API 根地址（如 `/v1`），也可填完整 `/chat/completions` 地址。不假设具体供应商；真实兼容性须用提供的服务联调。如果服务不支持 `response_format`，设置 `config.json` 中 `llm.json_mode=false`。接口只能用 HTTPS，本地开发地址允许 HTTP。

当前配置使用 `max_completion_tokens=4096`、`reasoning_effort=low`，不传 `temperature`。可在 `config.json` 中调整；普通兼容模型如只接受 `max_tokens`，将 `llm.token_limit_parameter` 改为 `max_tokens`。

```powershell
# 给已有论文生成摘要，不重复抓取
python run.py summarize

# 日常一键更新：采集、去重、摘要、导出
python run.py run

# 自定义日期窗口；日期按 UTC，默认使用脚本实际运行日期
python run.py run --days 30 --until 2026-09-26

# 只从已有归档重新构建前端数据
python run.py build
```

## 可复用 Skill

源文件：[`skills/gnn-paper-digest/SKILL.md`](skills/gnn-paper-digest/SKILL.md)。它指导后续 agent 运行、修改、验证本项目，不是定时任务的必需依赖。

2025/2026 年图学习相关 CCF-A 会议官网与论文源的可抓取性调查见 [`docs/CCF_A_SOURCES.md`](docs/CCF_A_SOURCES.md)；其中的只读探针与来源清单不参与当前正式搜索流程。

```powershell
python scripts/install_skill.py
```

安装到 `$CODEX_HOME/skills/gnn-paper-digest` 或默认 `~/.codex/skills/gnn-paper-digest`。在本项目目录中调用 `$gnn-paper-digest` 即可。安装器遇到内容不同的既有同名 skill 会停止，防止覆盖用户已有版本。

## 最新会议独立补漏审计

最新会议的 TAG/OOD 补漏结果、逐会议届次和未解决范围见 [`docs/latest_conference_coverage_audit.md`](docs/latest_conference_coverage_audit.md)。本轮按各会议最新已公开可核验届次选择 2026 或 2025，扩展到 ICLR、LoG、ICDM、WSDM、NAACL；旧归档保留。参考目录只用于发现，入库仍需主会来源、全文及逐字证据。访问失败不等于未公布，未取得正文的候选不生成猜测总结。

```powershell
# 恢复已有全文的待总结条目；显式加 --retry-failed 才重试历史请求失败
python -X utf8 scripts/summarize_literature_candidates.py --limit 150
# 仅去重、校验并导出已完成结果（不调用模型）
python -X utf8 scripts/publish_literature_audit.py --final
python -X utf8 scripts/report_literature_audit.py
```

审计缓存位于本机 `.local/literature-audit/`，恢复依赖这些文件；远程仓库不包含全文审计缓存。待处理清单在 `data/literature_pending.json`，恢复脚本不会自动重新抓取它们。普通 `run.py search` 仍是独立的预算检索入口，不代表本轮目录审计的全部覆盖。

## GitHub Pages 发布

本机完成检索后，`search`/`run` 会自动调用 `export_site`，把归档论文写入 `site/data/papers.json`；页面通过相对路径读取该文件，所以新卡片会随静态索引一起渲染。提交代码时要同时提交 `data/` 和 `site/` 的变更，再推送到 `main`，Pages Source 选择 GitHub Actions，`pages.yml` 会在 `site/**` 变化时发布。保留 pages.yml（静态发布）与 test.yml（Windows/Linux测试）；原 update.yml 自动采集已移除，不需要远程 LLM Secret。

## 旧流水线配置与处理约束

`config.json` 可调整查询词、回溯天数、启用来源和处理预算。

| 配置 | 默认 | 含义 |
| --- | --- | --- |
| `days` | 14 | 重叠回看最近 14 天，依靠持久归档去重 |
| `max_per_source` | 150 | 单来源本轮候选抓取上限；RSS回退按订阅源处理 |
| `max_llm_papers` | 50 | 单次最多总结 50 篇，积压留给下次 |
| `max_llm_seconds` | 1200 | 总结阶段软时间预算；到期不再开始新论文 |
| `llm_concurrency` | 3 | 同时处理的论文数，主线程统一保存结果 |
| `llm.attempts` | 3 | 每篇最多调用次数，包含请求或校验失败重试 |
| `sources.openalex` | false | 提供 OpenAlex key 后可开启 |

arXiv 使用官方 API 按更新时间检索；故障时回退最近 RSS 公告，明确标记不能补齐完整时间窗口。Crossref 按发表日期检索；OpenAlex 是额外的学术索引适配器。查询词过滤是候选召回，最终相关性由 LLM 判断。最近更新的旧论文可能进入采集窗口，页面日期仍保留原始发表日期。

**去重**：规范化 DOI、去版本 arXiv ID、来源 ID、去空白/标点及大小写差异后的完整标题。传递合并并持久保存所有身份别名，保留多个来源链接。避免宽松模糊标题匹配误合并不同研究；没有共有标识且改标题的版本可能仍重复，这是待增强的实体匹配范围。

**LLM**：提示词集中在 [`prompts/summarize.zh.txt`](prompts/summarize.zh.txt) 和 [`prompts/search.summary.zh.txt`](prompts/search.summary.zh.txt)，可直接修改。程序将核验后的论文全文提供给模型，检查 JSON、1至5个唯一短语、151至200个可见字符、1至4处加粗及逐字全文证据；无法获取全文时不生成推测卡片。

**缓存**：标题、摘要与取得的全文内容哈希 + 提示词哈希 + 模型名 + 推理强度共同决定是否重用。换提示词、模型或推理强度会使旧缓存失效；预算不足的重算任务显示为待处理。缺全文或信息不足时不猜测。

**正文与来源**：`search` 优先获取 arXiv HTML，否则解析可用论文 PDF，读取完整可提取正文后生成151至200个可见字符的加粗方法总结，不依赖摘要或方法章节标题；正文过短、无法提取或超过安全大小时拒绝生成新版卡片。KDD、WWW、SIGIR、SIGMOD、VLDB、ICDE、ACM MM 的会议目录用于初筛标题，再让搜索代理按精确标题寻找 arXiv。目录标题不能代替正式发表日期；目录到 arXiv 的结果默认只计 arXiv 配额。历史卡片保留旧总结，下一次处理时按全文缓存重新核验。兼容的旧 `run/summarize` 入口也要求取得全文才能生成新卡片。全文有大小和时间预算；检索不保证覆盖全网。

## 文件位置

```text
gnn_digest/           Python流水线与来源适配器
  vendor/             固定版本的上游RSS解析代码及许可证
prompts/              LLM提示词
skills/               可复用agent skill
data/papers.json      持久归档、摘要、去重身份、LLM缓存
data/last_run.json    最近运行覆盖范围与故障状态
site/                 可直接部署的静态站点
site/data/papers.json 前端精简数据，不包含原摘要、证据或密钥
tests/                去重、LLM校验、HTTP和运行恢复测试
docs/RESEARCH.md      同类项目调研、复用决策与官方资料
memory.md             开发记忆、当前状态、验证记录、待办
```

不要删除 `data/papers.json`，它是跨次去重和缓存的依据。JSON写入采用原子替换，单机运行用排他锁，GitHub工作流共用并发组。如进程被强制结束，检查已无任务在运行后才能删除残留的 `data/pipeline.lock`。

## 验证

```powershell
python -m unittest discover -s tests -v
node --check site/app.js
```

测试使用临时目录与本地HTTP模拟服务，不调用付费模型，也不污染真实归档。网络实测与真实模型联调状态请查阅 `memory.md`。

## 复用与许可

本项目自有代码采用 MIT。复用了 `yang3kc/daily_arxiv_digest` 的 RSS 解析脚本，原文件及MIT声明保留在 `gnn_digest/vendor/`，固定上游提交见 `PROVENANCE.json`。未直接复制其他项目的页面或LLM摘要代码。

论文元数据、原摘要和生成内容不因为仓库MIT许可而自动改变原有权利；代码许可不覆盖第三方论文内容。

会议适配：AAAI解压gzip页面并识别Technical Tracks；NeurIPS使用主会URL与论文集元数据，排除Creative AI等其他track；ACM/DOI详情受阻时核对出版方登记的Crossref proceedings-article元数据。需要替代全文时对`fulltext_url`的arXiv标题独立核验；arXiv仅提供正文，不能证明会议身份。

中断后续跑：`python -X utf8 run.py search --limit 100 --resume`。仅在没有活动进程、结果ID与批量检查点一致且目标/窗口相同时续跑，已完成批次不重复；原时间与全文处理预算累计。不要在仍有运行进程时删除锁。论文正文获取可对已核验会议标题发起精确arXiv API匹配，再独立核对arXiv标题；这一步只补全文，不产生固定关键词的发现搜索，也不占arXiv名额。

补搜与日期说明：首轮会为尚未检查的会议/年份分配名额，再进行有限补搜；已核验论文按持久ID、DOI、arXiv ID和规范题名跨批去重。同一会议的拒绝原因会反馈给下一次补搜，已修复的历史解析错误不再当作当前限制。批内截止日期固定为任务起始UTC日，避免跨午夜时范围漂移。

站点格式：ACL/EMNLP支持main、long、short主会编号，排除Findings等其他轨道；WWW兼容ACM on Web Conference正式名称。SIGMOD/PVLDB的期刊式论文集必须有出版方DOI与对应会议正式名单的双重证据；VLDB原始PDF从官网卷目录的结构化数据定位，不以ACM镜像可用性代替正文是否存在。OpenReview投稿论坛本身不证明录用。

页面区分“正式发表”和ICML节目页的“官网公布”，保留年/月精度；届次年份与日期年份不同会单独显示届次，会议徽标仍只有简称。总结仍依据全文，151–200个可见字符、1–4处方法加粗、TAG/OOD主题均不因补搜而放宽。

供应商网络超时会保存结果并停止，避免自动重发整轮付费请求；明确续跑时，失败范围缩小为最多4篇/4次工具调用目标，整体100篇配额不变。可从data/bulk_run.json查看完成批次与失败位置，停止原因必须区别于“范围内不存在论文”。
