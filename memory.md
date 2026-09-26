# Awesome-GNN 开发记忆

最后更新：2026-09-26。工作目录 `D:\Awesome-GNN`。

## 用户目标与约定

无人值守批量发现最新GNN论文，LLM生成按重要性排序的5个关键词及100字内中文核心方法；跨来源、跨次运行去重；GitHub存储、GitHub Pages静态展示。用户要求可复用skill，开发过程保留memory.md，并在一轮完成后统一提供API/仓库配置。

默认以论文**标题+摘要**为事实来源，不声称已读全文。方法限制按Unicode字符计数，包括标点、英文和数字。关键词与方法必须由LLM生成；无API时只采集元数据，不造摘要。

## 当前完成

- Python 3.11标准库流水线：`python run.py run|summarize|build`。
- arXiv API（分页、更新时间窗口）与RSS回退；Crossref官方API；OpenAlex可选适配器（Bearer key），默认关闭。
- DOI、去版本arXiv ID、来源ID、规范化完整标题的传递合并；持久身份别名，保留各来源链接。
- 可编辑提示词 `prompts/summarize.zh.txt`；JSON结构、恰好5个不同关键词、中文100字符限制、逐字证据校验；最多3次重试。
- 内容/提示词/模型缓存；原子JSON写入、逐篇checkpoint、单机锁、论文数及软时间预算。
- 静态前端：搜索、关键词筛选、来源/时间/状态筛选、排序、分页、移动布局；用textContent渲染不可信元数据，外链限制HTTP(S)。
- GitHub Actions：双平台测试、每日09:20北京时间采集与直接Pages发布、main静态文件更新发布。无远程执行记录。
- 复用skill源文件 `skills/gnn-paper-digest/SKILL.md`；安装器 `scripts/install_skill.py` 已运行，安装到 `C:\Users\19878\.codex\skills\gnn-paper-digest\SKILL.md`。
- `README.md`（中文运行与部署说明）、`docs/RESEARCH.md`（调研）、`.env.example`、MIT与第三方声明。
- 已在本目录初始化 Git `main`，远程为 `https://github.com/LiuJiaChen0x3f/Awesome-GNN.git`；提交 `049fbeb` 已推送到 `main`。

## 调研与实际代码复用

对比 yang3kc/daily_arxiv_digest、DaizeDong/Daily-ArXiv-Assistant、dw-dengwei/daily-arXiv-ai-enhanced。实际复用第一个项目的MIT RSS解析脚本；没有完整fork其他应用。上游提交 `9d19de2534fa9d89c3904128891779a2d32056d8`，原脚本与版权声明在 `gnn_digest/vendor/`，来源在 `PROVENANCE.json`。其他功能围绕本需求实现，详见调研文档。

## 已验证（2026-09-26）

1. **真实联网采集两次**，UTC日期窗口2026-09-13至2026-09-26：arXiv返回77条、筛出74条候选；Crossref返回148条、筛出13条候选。87条候选去掉6条重复，归档81篇。77篇含摘要待LLM，4篇无摘要。Crossref达到查询预算，上限状态已公开。
2. 第二次同窗口运行仍81篇，所有论文ID集合不变；不是只用mock证明去重。
3. **18项Python unittest全部通过**：版本去重、DOI/标题传递合并、身份别名跨次保存、新短摘要优先、缓存重用/失效、日期过滤、摘要校验、请求失败不造数据、单源失败隔离、全源失败保存旧归档、倒排摘要恢复、本地HTTP Chat Completions端到端及第二次零模型请求。
4. `node --check site/app.js` 与Python compileall通过。
5. skill官方校验通过。Windows默认GBK读取中文曾失败，改用 `python -X utf8 .../quick_validate.py skills/gnn-paper-digest` 即通过，不是skill内容问题。
6. 本地浏览器实测：81篇真实数据呈现；搜索Hermite得到1篇；Crossref筛选7篇；加载更多由30到60篇；无匹配提示正确；390px手机布局无横向溢出。桌面和手机视觉检查完成。
7. 三份workflow通过YAML解析。另在gitignored的`.local/ui-fixture`中测试完成态卡片与关键词，不写入真实归档。

## 本轮真实运行结果

- 已配置并联调 `https://yundou.ai/v1` 的 Chat Completions 兼容接口，模型为 `gpt-6-astra`，推理强度 `medium`；API key 仅保存在本机 `.env` 和 GitHub Actions 加密 Secret `LLM_API_KEY`，不写入仓库。
- 真实模型第二轮处理完成：总计81篇，75篇 `ready`，2篇 `irrelevant`，4篇 `missing_abstract`，无待处理摘要。`site/data/papers.json` 已由 `python run.py build` 导出。
- GitHub Actions 变量 `LLM_BASE_URL`、`LLM_MODEL`、`LLM_REASONING_EFFORT` 与 Secret `LLM_API_KEY` 已配置；Pages 设置为 GitHub Actions 模式，目标地址为 `https://liujiachen0x3f.github.io/Awesome-GNN/`。
- 本轮界面与检索优化：移除首屏图形宣传区，放大论文工作区；卡片新增 venue 与会议/期刊类型；arXiv 卡片优先打开 PDF，其他来源打开论文页面；Crossref 优先请求 `proceedings-article`；提示词加入 CCF GNN 高频术语词表（消息传递、图卷积、图注意力、图Transformer、异质图、图对比学习、图结构学习、节点分类、链路预测等）。
- 按用户要求进行了两轮每轮 3 篇真实采集/LLM 验证。最终归档 89 篇，其中 79 篇 arXiv 预印本、3 篇会议论文、3 篇期刊、2 篇书章、2 篇未标注类型；本轮样例包含 Hermite 谱图网络、GNN 形式化验证、IMU-ECG 图编码。新增 venue 仅在源元数据提供时显示，CCF 会议名称不能从 arXiv 元数据可靠推断。
- 新提示词全量重算后状态为：80 篇 `ready`、2 篇 `irrelevant`、1 篇 `insufficient`、1 篇 `failed`、5 篇 `missing_abstract`；失败项不发布模型猜测，后续运行自动重试。
- 最终检查：18 项 unittest、`node --check site/app.js`、`python run.py build`、`git diff --check` 均通过。
- 检索逻辑已改为 LLM 动态规划：`SearchPlanner` 使用 `prompts/search.en.txt`，每次根据日期窗口、GNN主题和 CCF venue 生成4至8个检索短语，再传给 arXiv/Crossref；`data/last_run.json` 保存本次 `search_queries`。固定 `config.json` 查询词仅作为无LLM采集时的兼容回退，不参与正常 LLM 检索。
- 动态检索真实验证：LLM 生成 8 个短语，arXiv 28 个候选、Crossref 4 个候选；3篇验证预算下因已有缓存实际重算1篇，其余结果复用有效缓存。

## 当前真实限制

- 推送后的 GitHub Actions `Test pipeline` 与 `Publish site` 均已成功；Pages API 显示 workflow 模式，线上 `https://liujiachen0x3f.github.io/Awesome-GNN/` 返回 HTTP 200。每日 `Update paper digest` workflow 已随代码启用，首次定时运行仍受 GitHub 计划任务延迟影响。
- 没有OpenAlex key，该适配器未做真实认证联调。官方现有文档允许低额度匿名查询，本项目为无人值守规模访问主动要求key；不要说所有OpenAlex查询都必须key。
- 没有远程仓库地址，GitHub Actions与Pages尚未实际部署验证。
- 搜索召回并非全网，Crossref本轮截断；源日期精度可能不同。RSS回退只覆盖公告窗口，使用公告日期并标记date_basis。arXiv按更新日期抓取，旧论文新版本可能收录，但页面显示原发表日期。
- 同一论文无共有ID且更换标题时，严格去重可能遗漏；不同论文完全同名也可能合并。当前不使用激进模糊匹配，避免更多误合并。后续可加作者/年份约束和可审计实体匹配。
- 每次默认最多50篇/约20分钟软LLM时间预算，剩余任务留给下次。持续大量新增可能积压，需调整预算。重试可能额外花费，API价格待选定供应商后确认。
- 缺少摘要的论文目前不自动下载PDF，避免捏造；如需全文模式，需另做开放全文获取、解析和成本控制。
- `.env`只支持简单KEY=VALUE、整行注释和包裹引号，不做shell展开。不可提交密钥；前端不调用模型。
- 外部字体加载失败时使用系统字体，不影响功能。

## 下一轮最小输入

1. 若更换供应商，更新本机 `.env` 与 GitHub Actions Secret/Variables，并重新运行 `python run.py summarize`。
2. 若扩大来源或全文摘要，先更新 `config.json` 与提示词，再保留现有 `data/papers.json` 做增量运行。

## 快速定位

- 采集与日期：`gnn_digest/sources.py`
- 去重与身份：`gnn_digest/models.py`
- 提示词/LLM：`prompts/summarize.zh.txt`、`gnn_digest/llm.py`
- 运行预算/状态：`gnn_digest/cli.py`、`config.json`
- 原子保存/前端导出：`gnn_digest/storage.py`
- 前端：`site/index.html`、`site/style.css`、`site/app.js`
- 部署：`.github/workflows/`
- 验证：`tests/test_pipeline.py`

本轮预览服务绑定`127.0.0.1:8000`。若已结束，用 `python -m http.server 8000 --bind 127.0.0.1 --directory site` 重启。
