# Awesome-GNN 开发记忆

最后更新：2026-09-27。工作目录 `D:\Awesome-GNN`。

## 用户目标与约定

本地按固定研究需求发现最新GNN论文，LLM生成按重要性排序的5个关键词及100字内中文核心方法；跨来源、跨次运行去重；GitHub存储、GitHub Pages静态展示。用户要求可复用skill，开发过程保留memory.md。

默认以论文**标题+摘要**为事实来源，不声称已读全文。方法限制按Unicode字符计数，包括标点、英文和数字。关键词与方法必须由LLM生成；无API时只采集元数据，不造摘要。

## 当前完成

- 2026-09-27 ICML/ICLR官网可达性只读实测：两站2026列表及各一篇poster详情均HTTP200，详情正文有摘要/OpenReview链接；ICLR proceedings样例含发表日和PDF元数据。当前DOMAINS未接入icml.cc/iclr.cc/openreview.net，VENUES未纳入ICLR，现有通用解析器也不适配详情正文。现有模型接口第二次探测45.55秒有8个实际工具动作并返回两站论文引用，首次仅instructions传具体任务时无工具动作，不能称成功。详见docs/CONFERENCE_SOURCE_PROBE.md；本次没有修改搜索逻辑、会议准入、配额或归档，也没有进行三篇正式采集。

- 2026-09-26 来源配额更新：`search --limit N` 强制会议 ceil(N/2)、arXiv floor(N/2)，10为5+5，3为2+1。会议仍为项目允许的CCF-A主会+EMNLP主会；arXiv不限会议等级。`agent.py` 保存各自独立核验路线，结合历史身份别名跨组去重，同一论文最多一个名额；按分配路线的日期排序，缺额定向反馈补搜，不跨组补足、不扩大窗口。归档checkpoint保留已保存论文；selection_bucket仅在本次结果，历史归档不强制1:1。
- 配额同步到 `prompts/search.request.txt`、`prompts/search.agent.txt`、README和已安装skill；报告新增source_quotas/quota_progress/每轮quota_before与quota_after。网页显示会议与arXiv各自完成数，并把“未补齐目标”与旧采集的抓取上限区分。
- 本轮测试新增 `tests/test_quotas.py`，覆盖5+5、单来源不足、奇数、双路线分配、历史别名桥接、失败摘要、补搜、避免无用摘要调用；44项unittest通过，node语法及skill校验通过。真实验证发现引用标题带站名后缀，已仅对ACL Anthology/IJCAI匹配域名清理已知后缀，仍要求与原站元数据标题完全规范化匹配。
- 两次真实 `search --limit 3`：均为2026-09-13至2026-09-26 UTC窗口、3轮补搜，最终会议0/2、arXiv1/1，未达标。首轮186.08秒；标题后缀修复后的最终轮195.08秒，返回ARGUS（2609.30184），新总结1篇，复用归档ID，归档仍94篇。会议候选遇到原站摘要不可用、URLError及目录页不匹配，不能由此声称窗口内不存在会议论文。结果/拒绝详情保存在data/search_results.json与data/last_run.json；没有扩大日期或用额外arXiv填缺额。网页本地实测显示“会议0/2；arXiv1/1”和预算不足提示，保留历史归档。密钥扫描、结果唯一性/五关键词/百字限制通过。

- 推荐入口已升级为 `python run.py search --limit 3`：`agent.py` 使用 Responses web_search 搜索/打开网页，按原站核验反馈继续检索；旧 `run` 仍为兼容批处理，不能混同。`verification.py` 校验受限主站URL、精确标题、原始摘要、日期及会议主会信息。新字段含 topics、topic_evidence、publication_events、display_date、venue_label、pdf_url。归档不删除，旧记录不强制重算。
- 当前用户需求仍读 `prompts/search.request.txt`；代理规则为 `search.agent.txt`，单篇总结为 `search.summary.zh.txt`。`search.en.txt` / `summarize.zh.txt` 仅用于旧入口。结果不足退出4，网络失败退出2；结果和详细工具轨迹在 `data/search_results.json` / `data/last_run.json`。
- 供应商兼容性：实测添加 max_tool_calls 返回HTTP400，故默认不发送（send_max_tool_calls=false）。轮数/输出token有程序限制，单轮工具次数仅提示词目标，时间为软预算。store=false/instructions在完整实测成功，接口失败不自动重复付费搜索。
- 2026-09-26 完整联调：第一次有效运行3轮约220秒，3篇均经原站验证且新生成摘要；修复中间消息解析并增加引用候选恢复后，第二次1轮50.06秒返回同3篇、0次摘要重算、无重复入库。论文为 arXiv:2609.30150、2609.30173、2609.30184，均核验v1日期2026-09-24。共31项测试通过，node语法检查及skill校验通过；网页实测GridSFM搜索、KG筛选、arXiv简称、首次提交日期及PDF链接正确。
- 本轮开始时用户工作区已有93篇归档及数据改动（包括85篇pending）；已备份到 `.local/pre-agent-backup`，保留已有改动后归档94篇，4 ready、83 pending、5 missing_abstract、2 irrelevant。pending不是本轮全量失效造成的；本轮只处理搜索选中的论文。不要把旧历史数据描述为已按新准入规则核验。
- 限制：会议网页缺精确日期/结构化会议名、站点拒绝访问时会保守拒绝，当前真实样例只验证了arXiv路线，会议路线有模拟测试但尚无本轮真实合格样例。网页默认最新排序但保留历史归档；搜索是预算内最佳努力，不保证全网最新前三。依旧只读摘要，未实现PDF全文理解。

- Python 3.11标准库流水线：`python run.py run|summarize|build`。
- arXiv API（分页、更新时间窗口）与RSS回退；Crossref官方API；OpenAlex可选适配器（Bearer key），默认关闭。
- DOI、去版本arXiv ID、来源ID、规范化完整标题的传递合并；持久身份别名，保留各来源链接。
- 可编辑提示词 `prompts/summarize.zh.txt`；JSON结构、恰好5个不同关键词、中文100字符限制、逐字证据校验；最多3次重试。
- 内容/提示词/模型缓存；原子JSON写入、逐篇checkpoint、单机锁、论文数及软时间预算。
- 静态前端：搜索、关键词筛选、来源/时间/状态筛选、排序、分页、移动布局；用textContent渲染不可信元数据，外链限制HTTP(S)。
- GitHub Actions：保留测试与Pages发布；论文采集只在本机交互式执行，不再使用定时任务。
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

- 已配置并联调 `https://yundou.ai/v1` 的 Chat Completions 兼容接口，模型为 `gpt-6-astra`，推理强度 `medium`；交互式搜索只从本机 `.env` 读取 API key，不写入仓库。
- 真实模型第二轮处理完成：总计81篇，75篇 `ready`，2篇 `irrelevant`，4篇 `missing_abstract`，无待处理摘要。`site/data/papers.json` 已由 `python run.py build` 导出。
- Pages 设置为 GitHub Actions 模式，目标地址为 `https://liujiachen0x3f.github.io/Awesome-GNN/`。
- 本轮界面与检索优化：移除首屏图形宣传区，放大论文工作区；卡片新增 venue 与会议/期刊类型；arXiv 卡片优先打开 PDF，其他来源打开论文页面；Crossref 优先请求 `proceedings-article`；提示词加入 CCF GNN 高频术语词表（消息传递、图卷积、图注意力、图Transformer、异质图、图对比学习、图结构学习、节点分类、链路预测等）。
- 按用户要求进行了两轮每轮 3 篇真实采集/LLM 验证。最终归档 89 篇，其中 79 篇 arXiv 预印本、3 篇会议论文、3 篇期刊、2 篇书章、2 篇未标注类型；本轮样例包含 Hermite 谱图网络、GNN 形式化验证、IMU-ECG 图编码。新增 venue 仅在源元数据提供时显示，CCF 会议名称不能从 arXiv 元数据可靠推断。
- 新提示词全量重算后状态为：80 篇 `ready`、2 篇 `irrelevant`、1 篇 `insufficient`、1 篇 `failed`、5 篇 `missing_abstract`；失败项不发布模型猜测，后续运行自动重试。
- 最终检查：18 项 unittest、`node --check site/app.js`、`python run.py build`、`git diff --check` 均通过。
- 检索逻辑已改为 LLM 动态规划：`SearchPlanner` 使用 `prompts/search.en.txt`，每次根据日期窗口、GNN主题和 CCF venue 生成4至8个检索短语，再传给 arXiv/Crossref；`data/last_run.json` 保存本次 `search_queries`。固定 `config.json` 查询词仅作为无LLM采集时的兼容回退，不参与正常 LLM 检索。
- 动态检索真实验证：LLM 生成 8 个短语，arXiv 28 个候选、Crossref 4 个候选；3篇验证预算下因已有缓存实际重算1篇，其余结果复用有效缓存。
- 新增本地交互式搜索：编辑 `prompts/search.request.txt` 后运行 `python run.py search --limit 5`，固定文件内容作为用户研究需求，由 LLM 规划并直接返回多篇结果；动态查询现在会同时传入 arXiv/Crossref/OpenAlex 适配器，而不是只用于本地过滤。该模式不依赖 GitHub Actions，API 配置只从本机 `.env` 读取。
- 交互式搜索真实验证：`search --limit 3` 生成 8 个查询，arXiv/Crossref 分别返回 3/2 个候选，并输出 3 个结果；由于摘要缓存，本轮实际新总结 1 篇。
- 本轮仅丰富提示词，未运行采集：搜索范围限定为前 11 个热点缩写（GNN、SSL、CL、OOD、TAG、GSL、HGT、TGN、KG、KGE、HGNN），提示词要求 CCF-A 会议和来源元数据验证，并要求网页会议标签使用简称；实际 CCF-A 过滤与简称归一化留待下一轮代码改动。
- 根据用户最新要求，删除 `.github/workflows/update.yml`：不再计划或远程手动触发自动采集；仅在本机执行 `search`，然后按需手动提交站点数据。既有 GitHub Actions Secret 不再由该项目工作流读取。

## 当前真实限制

- 本轮CI修复：Ubuntu测试通过，Windows因直接调用search函数绕过CLI的UTF-8设置而打印中文失败。已在search入口统一UTF-8，并在本机PYTHONIOENCODING=cp1252环境复测；与检索业务规则无关，无须额外付费采集。

- 2026-09-26 快速接口实测（本机当前 gpt-6-astra / medium 配置，共 4 次 HTTP 请求）：Chat Completions 自定义 function tool 强制调用返回正确参数，回传随机 receipt 后模型正确读取，完整往返通过；Responses + `tools: [{"type":"web_search"}]` 返回 completed 的 search/open_page 两次工具记录及 URL 引用，arXiv 标题另行核对一致；Chat Completions + `web_search_options` 虽返回 HTTP 200，但无引用且回答搜索不可用，此路径未通过。测试脚本和脱敏报告位于 gitignored `.local/probe_capabilities.py`、`.local/capability_probe_report.json`。这证明当前接口的最小能力，不代表所有搜索参数或复杂代理流程已验证；尚未接入正式论文流程，未修改论文数据。

- 2026-09-26 后续提示词调整（覆盖此前排除未录用预印本的规则）：纳入来源为 CCF-A 主会、EMNLP 主会或独立核验的 arXiv 记录；arXiv 不限制会议等级或录用状态，11 个主题 OR 条件保留。arXiv 用 v1 首次提交日期，会议用正式发表日期；两种来源合并后保留日期依据，按窗口内较新的合格事件排序且只返回一条。无已核实合格会议时标签为 arXiv。本轮仅修改两份搜索提示词和 memory.md，未运行检索/LLM，未修改数据、前端或日期过滤代码。

- 2026-09-26 提示词补充：允许范围调整为 CCF-A 主会 + EMNLP 主会（唯一 B 类例外，不含 Findings/workshop）；保持 11 个主题 OR 匹配，按正式会议论文发表日期从新到旧检索、去重后限量，修订/抓取日期不代替发表日期。本轮只改 `prompts/search.request.txt`、`prompts/search.en.txt` 和本记录，未调用 LLM、未采集、未改网页或数据。现有采集代码尚未严格执行这些约束，arXiv 仍按更新日期抓取；后续实现需要会议身份核验、正式发表日期字段及排序对齐。

- 推送后的 GitHub Actions `Test pipeline` 与 `Publish site` 均已成功；Pages 使用 workflow 模式，线上 `https://liujiachen0x3f.github.io/Awesome-GNN/` 返回 HTTP 200。自动采集 workflow 已按用户要求移除。
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
