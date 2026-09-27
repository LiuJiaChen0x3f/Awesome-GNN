# Awesome GNN · 图学习研究雷达

## 推荐入口：本地联网搜索代理

```powershell
cd D:\Awesome-GNN
# 修改固定研究需求，不必填写检索词
notepad prompts/search.request.txt
python run.py search --limit 3
# 默认最近14天；可改窗口
python run.py search --limit 3 --days 30
```

本机 `.env` 使用既有 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL / LLM_REASONING_EFFORT。`search` 现通过 **Responses + web_search** 让模型搜索、打开论文网页；不走旧的“先生成检索词再固定抓取”。每轮返回候选后，程序独立读取原站，核验标题、摘要、日期、会议；反馈拒绝原因和缺口，让模型继续搜索。最后通过 Chat Completions 生成5个关键词、百字方法及有原文证据的1至11个主题。没有合格结果不会凑数。

收录：项目列出的CCF-A主会 + EMNLP主会，或独立核验的arXiv论文（不限会议等级）。11主题任意命中一个即可，KG/KGE不强制使用GNN。arXiv用v1首次提交日，会议用正式发表日；不以修订日期冒充新论文。来源缺精确日期/会议元数据时拒绝并反馈，不根据模型声称的事实放行。主站域名和会议别名在 `gnn_digest/verification.py`，它不是完整CCF-A目录。

输出：`data/search_results.json` 保存本次合格论文；`data/last_run.json` 保存每轮工具动作、引用、拒绝原因、用量与停止原因；`data/papers.json` 持久去重归档，`site/data/papers.json` 是网页数据。网页默认最新优先、来源标签使用简称/arXiv、链接PDF优先；历史归档仍在，旧记录不声称已经新规则复核。

`--limit` 是1至20篇的目标数量，覆盖需求文件内的示例数量。退出码0达到目标，4表示有搜索但不足，2表示联网搜索未成功。搜索排序是预算内的最佳努力，不能宣称全网最新排名。源码、测试和归档均不含密钥。

**来源各占一半**：`python run.py search --limit 10` 要求5篇会议 + 5篇arXiv。奇数时会议多1篇，所以 `--limit 3` 是2篇会议 + 1篇arXiv，`--limit 1` 只找会议。会议仍须为上述合格主会；arXiv不限会议等级或录用状态。每组按各自发表日期优先检索，跨组去重，同一论文不能占两个名额。缺少会议时会继续定向搜索会议；达到预算仍不足，就报告各组缺额并退出4，不以arXiv补足，不静默扩大日期窗口。报告中的 `source_quotas` / `quota_progress` 及本次结果的 `selection_bucket` 可用于核对；历史归档不要求整体1:1。

`config.json.search_agent` 默认3轮、单请求超时180秒、总软预算600秒、每轮10候选、10篇摘要预算（目标更大时至少为目标数）。超时不会自动重发付费搜索。当前供应商拒绝可选 `max_tool_calls` 参数，默认 `send_max_tool_calls=false`；12次/轮是提示词目标，不是硬上限。外层限制轮数、输出token和时间；只有供应商确认支持后才开启该参数。

提示词：`search.request.txt` 是用户需求，`search.agent.txt` 是搜索执行与JSON格式，`search.summary.zh.txt` 是核验摘要的总结规则。全文PDF解析尚未实现。API需支持Responses联网搜索和Chat Completions摘要，不能仅凭模型名认定兼容。

只保留测试和静态Pages发布工作流，**没有每日采集任务，无需远程保存模型密钥**。本机运行后按需提交并推送网页数据。以下旧 `run` / `summarize` 命令作为兼容入口保留，不具有新 `search` 的完整核验流程。

自动查找近期 GNN 论文，用 **5 个关键词 + 100 字以内的中文核心方法** 帮读者快速筛选。本地手动发起后自动完成搜索、核验、去重和摘要。

后端 Python 3.11+，**零第三方运行依赖**；前端 HTML/CSS/JavaScript，无需 Node 构建或服务器，部署到 GitHub Pages。

> 已接入真实 LLM 接口并验证方法卡片生成；使用 `gpt-6-astra`、中等推理强度。密钥仅从环境变量或本机 `.env` 读取，不随仓库发布。数据状态与覆盖范围见页面及 `data/last_run.json`。

## 兼容入口：旧批处理

在仓库根目录运行：

```powershell
# 不需要 pip install，先抓取真实数据
python run.py run --no-llm

# 预览页面，然后浏览器打开 http://localhost:8000
python -m http.server 8000 --directory site
```

复制 `.env.example` 为 `.env`，填写你自己的兼容 Chat Completions 的服务：

```dotenv
LLM_BASE_URL=https://your-provider.example/v1
LLM_API_KEY=你的密钥
LLM_MODEL=你的模型名
LLM_REASONING_EFFORT=medium
```

`LLM_BASE_URL` 既可填 API 根地址（如 `/v1`），也可填完整 `/chat/completions` 地址。不假设具体供应商；真实兼容性须用提供的服务联调。如果服务不支持 `response_format`，设置 `config.json` 中 `llm.json_mode=false`。接口只能用 HTTPS，本地开发地址允许 HTTP。

当前配置使用 `max_completion_tokens=4096`、`reasoning_effort=medium`，不传 `temperature`。可在 `config.json` 中调整；普通兼容模型如只接受 `max_tokens`，将 `llm.token_limit_parameter` 改为 `max_tokens`。

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

## GitHub Pages 发布

本机完成检索后，按需把数据和静态页面提交到仓库 main 分支。Pages Source 选择 GitHub Actions。保留 pages.yml（静态发布）与 test.yml（Windows/Linux测试）；原 update.yml 自动采集已移除，不需要远程 LLM Secret。

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

**LLM**：提示词集中在 [`prompts/summarize.zh.txt`](prompts/summarize.zh.txt)，可直接修改。提示词由本项目预先编写并版本管理，不让模型每次运行自行改写检索和总结口径。按标题与摘要判断相关性、给关键词排序、描述方法，提供原摘要逐字证据。程序检查 JSON、5个唯一短语、中文方法长度和证据真实性。不自动截断超长描述；通过重试修正。

**缓存**：标题和摘要内容哈希 + 提示词哈希 + 模型名 + 推理强度共同决定是否重用。换提示词、模型或推理强度会使旧缓存失效；预算不足的重算任务显示为待处理。缺摘要或信息不足时不猜测。单篇失败会留下状态并在以后运行重试。

**边界**：当前以摘要为依据，不下载/阅读全文。不能保证百字概括覆盖论文所有方法，也不能保证检索覆盖全部学术网站。检索上限、源故障和RSS回退会显示在页面；缺摘要的论文仍可查到原文。

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
