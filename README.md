# Awesome GNN · 图学习研究雷达

自动查找近期 GNN 论文，用 **5 个关键词 + 100 字以内的中文核心方法** 帮读者快速筛选。采集、跨来源去重、相关性判断、LLM 总结、校验、增量保存和静态发布可以无人值守运行。

后端 Python 3.11+，**零第三方运行依赖**；前端 HTML/CSS/JavaScript，无需 Node 构建或服务器，部署到 GitHub Pages。

> 已接入真实 LLM 接口并验证方法卡片生成；使用 `gpt-6-astra`、中等推理强度。密钥仅从环境变量或本机 `.env` 读取，不随仓库发布。数据状态与覆盖范围见页面及 `data/last_run.json`。

## 本地开始

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

```powershell
python scripts/install_skill.py
```

安装到 `$CODEX_HOME/skills/gnn-paper-digest` 或默认 `~/.codex/skills/gnn-paper-digest`。在本项目目录中调用 `$gnn-paper-digest` 即可。安装器遇到内容不同的既有同名 skill 会停止，防止覆盖用户已有版本。

## GitHub Pages 与每日更新

1. 将项目推送到 GitHub 仓库的 `main` 分支。本项目仓库为 `LiuJiaChen0x3f/Awesome-GNN`。
2. 仓库 **Settings → Pages → Source** 选择 **GitHub Actions**。
3. **Settings → Secrets and variables → Actions** 设置：

| 类型 | 名称 | 用途 |
| --- | --- | --- |
| Secret | `LLM_API_KEY` | 模型密钥 |
| Variable | `LLM_BASE_URL` | 接口根地址或完整 Chat Completions 地址 |
| Variable | `LLM_MODEL` | 模型名称 |
| Variable，可选 | `LLM_REASONING_EFFORT` | 推理强度，默认使用配置中的 medium |
| Secret，可选 | `OPENALEX_API_KEY` | 启用 OpenAlex 时使用 |
| Secret，可选 | `CONTACT_EMAIL` | 数据源请求联系信息 |

4. 手动运行 **Update paper digest**。未接 API 时可勾选 `collect_only`。正常无人值守更新要求三个 LLM 配置全部有效。
5. 定时计划为每日 **01:20 UTC / 北京时间 09:20**。GitHub 托管计划任务可能延迟；长时间不活跃的公共仓库可能停用计划任务，需在 Actions 中恢复。

网站地址通常为 `https://<用户名>.github.io/<仓库名>/`。前端使用相对路径，兼容仓库子路径。

三个 workflow：

- `update.yml`：抓取与总结 → 保存数据提交 → 直接发布 Pages。直接部署避免机器人提交不触发后续 push workflow 导致页面不更新。
- `pages.yml`：初始 `main` 推送或修改静态页时发布，也支持手动运行。
- `test.yml`：Windows 与 Linux 上的 Python 测试、前端语法检查。

如果默认分支不是 `main`，修改 `pages.yml` 的分支触发配置。数据 workflow 会使用仓库默认分支。需要允许 workflow 写入仓库；若分支保护禁止机器人直接推送，需改为数据分支或 PR 流程。当前没有替你更改远程权限。

## 配置与处理约束

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
