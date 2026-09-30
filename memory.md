# Awesome-GNN 开发记忆

最后更新：2026-09-27。工作目录 `D:\Awesome-GNN`。

## 用户目标与约定

本地按固定研究需求发现最新GNN论文，LLM生成按重要性排序的1至5个关键词及200字内中文核心方法；总结依据可获取的论文全文，不再依赖摘要或方法章节标题；跨来源、跨次运行去重；GitHub存储、GitHub Pages静态展示。用户要求可复用skill，开发过程保留memory.md。

来源标题、日期和会议由程序独立核验；方法卡片必须先取得可提取的全文，再由LLM生成。方法限制按Unicode字符计数，包括标点、英文和数字。关键词与方法必须由LLM生成；无API时只采集元数据，不造总结。

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

- 2026-09-27 模型改为本机 `gpt-5.6-luna` / `low`（`.env` 不入库）；`config.json` 和 `.env.example` 同步默认低推理强度。搜索路径允许每篇总结最多两次格式修复并记录具体校验失败。IJCAI 主会页面的正文摘要提取、Main Track 核验及 24 MB PDF 上限已补齐；可实读 `2026/310` 论文约 11k 字符的方法章节。arXiv PDF 的 “Problem formulation and method” 标题也可识别。53 项 unittest 通过。
- 真实检索先以默认 14 天窗口运行 `search --limit 3`，结果 0/3；再以明确的 90 天窗口运行两次，仍均为 0/3。最后一次三轮中前两轮返回候选，第三轮供应商网络超时；arXiv 候选因方法正文或 LLM 输出校验失败，ACL 候选原站摘要未解析。`data/last_run.json`、`data/search_results.json` 保留最后一次真实失败报告，历史归档未用旧论文填充本轮配额。不能声称已检索成功 3 篇。后续优先处理 ACL 正文摘要解析和 low 模型的结构化输出稳定性，再做有界复验。

- 2026-09-27 方法总结与目录辅助检索升级：`gnn_digest/fulltext.py` 限量读取 arXiv HTML/论文 PDF，识别方法章节；`gnn_digest/llm.py` 校验 200 字以内方法总结和至少一段方法正文逐字证据，正文加入缓存哈希。`gnn_digest/agent.py` 向 Responses 传审计过的会议目录，支持目录标题初筛、arXiv 精确标题回查；`gnn_digest/verification.py` 再次读取目录核对标题。目录证据只辅助发现，不证明会议正式发表日期，也不自动占会议配额。旧 `run/summarize` 新卡片同样要求正文。历史卡片没有批量重算。
- 真实验证：两次 `python -X utf8 run.py search --limit 3`。首轮供应商返回候选，但论文方法章提取规则过窄，结果 0/3；已针对真实 arXiv `2609.28670` 的 “Graph Dynamics Model” 章节修正并单独读取成功（约 18k 字符）。第二轮 Responses 请求 `RequestError`，按不自动重复付费请求规则停止，0/3；两次都未满足 2 会议+1 arXiv，不得描述为成功。最新 `data/last_run.json` 记录第二轮故障。51 项 unittest 及 `node --check` 通过。下次服务恢复后需重跑三篇，核对摘要和方法章节证据。

- 2026-09-27 CCF-A 会议来源调研：`docs/CCF_A_SOURCES.md`；逐年入口 `docs/conference_sources.json`；只读探针 `scripts/probe_conference_sources.py`；抽样证据 `docs/conference_source_audit.json`。2025/2026 均有可读论文级内容的首批来源为 ICML、AAAI、IJCAI、ACL、CVPR；ICCV 仅 2025，NeurIPS 2025 可读而 2026 尚不可接入。其余站点有访问/元数据/主会身份限制，详见文档。本轮不改正式搜索逻辑或论文归档。正式接入时须解决 track、日期精度、PDF 与 arXiv 去重。

- 采集与日期：`gnn_digest/sources.py`
- 去重与身份：`gnn_digest/models.py`
- 提示词/LLM：`prompts/summarize.zh.txt`、`gnn_digest/llm.py`
- 运行预算/状态：`gnn_digest/cli.py`、`config.json`
- 原子保存/前端导出：`gnn_digest/storage.py`
- 前端：`site/index.html`、`site/style.css`、`site/app.js`
- 部署：`.github/workflows/`
- 验证：`tests/test_pipeline.py`

本轮预览服务绑定`127.0.0.1:8000`。若已结束，用 `python -m http.server 8000 --bind 127.0.0.1 --directory site` 重启。

## 2026-09-27 本轮全文总结改造

- `gnn_digest/fulltext.py` 新增 `load_fulltext`：优先读取 arXiv HTML，再回退论文 PDF，读取全部可提取页面，不再调用方法章节标题识别；正文过短、超过120000字符、超过24 MB/100页或标题不匹配时明确拒绝。正文只保存在本地归档，`site/data/papers.json` 不导出全文。
- `gnn_digest/verification.py` 不再因摘要缺失拒绝已核验来源；标题、日期、会议/主会轨道仍由原站元数据独立校验。`gnn_digest/llm.py` 与两份总结提示词改为只向模型提供全文，证据必须逐字来自全文，关键词放宽为1至5个且去重，方法保持200个Unicode字符上限。
- `agent.py`、兼容的 `run/summarize` 路径、缓存哈希和去重合并均迁移到 `full_text`；旧的 `method_sections`/`method_text` 记录不会被当作新全文缓存。页面状态文案改为“全文未获取/全文方法总结”。
- 本机 `.env` 已切换为 DeepSeek `https://api.deepseek.com`、`deepseek-flash`、low 推理；密钥不写入代码、日志、静态数据或 Git。已做模型列表和 Chat Completions JSON 探针，未在本记录写入密钥。
- 本轮代码测试：53 项 unittest 通过，覆盖全文加载兼容、1至5关键词、去重、配额和旧入口；`node --check site/app.js` 待本轮最终改动后再次执行。下一步是真实 `python -X utf8 run.py search --limit 3`，记录会议2篇 + arXiv1篇的完成数和全文/LLM拒绝原因；不足时不以历史归档补齐。

## 2026-09-27 DeepSeek 工具协议修复与复验

- DeepSeek 本地函数工具链继续使用 `https://api.deepseek.com`、`deepseek-flash`、`low`。问题根因不是密钥：模型一次返回超过本地预算的多个 `tool_calls` 时，旧代码只给前几个 ID 回复 tool message，下一请求因此返回 HTTP 400（`insufficient tool messages following tool_calls message`）。`gnn_digest/agent.py` 现在为预算外 ID 回复有界的空结果，不执行额外搜索；本地工具结果每次最多保留 4–8 条，每条摘要最多 400 字符，完整标题/URL仍由程序独立核验。最终格式化请求失败时也保留已完成工具线索继续核验。`gnn_digest/http.py` 记录脱敏的供应商错误短消息，避免把请求体或密钥写入报告。
- 新增函数工具协议回归测试；当前 `python -X utf8 -m unittest discover -s tests -v` 共 54 项通过，`node --check site/app.js` 与 `python -X utf8 -m compileall -q gnn_digest` 通过。
- 修复后真实运行 `python -X utf8 run.py search --limit 3`，UTC 窗口为 2026-09-14 至 2026-09-27，共 3 轮、每轮实际工具搜索完成，无供应商协议错误。结果为 **1/3**：会议 0/2（缺额 2），arXiv 1/1；arXiv 论文为 `Reachability-Based Formal Verification of Graph Neural Networks with Node and Edge Features`，v1 日期 2026-09-24，取得约 80k 字符全文并复用已有 DeepSeek 全文总结。会议候选因不在允许来源、正式日期超窗口或原站 HTTP 错误被保守拒绝，不能据此断言窗口内没有会议论文。`data/last_run.json` 和 `data/search_results.json` 保留完整缺额与拒绝原因，历史归档仍为 94 篇；网页只导出精简字段，不含全文或 API key。
- 代码已提交到本地 `main`（提交信息 `fix DeepSeek scholarly tool orchestration`）；尝试推送时 GitHub 凭据弹窗被取消，随后凭据复用脚本被本机安全策略拦截，因此远程尚未包含本轮提交。重新登录 GitHub 后执行 `git push origin main` 即可。

## 2026-09-27 LAYSO Responses 联网能力测试

- 按用户提供的配置，本机 `.env` 已切换为 `https://api.layso.ai/v1`、模型 `gpt-5.6-luna`、推理强度 `high`；Key 仅写入被 `.gitignore` 忽略的 `.env`，没有写入代码、报告、静态页面或 Git。
- 脱敏探针：`GET /models` 返回 HTTP 200；`POST /responses` 返回 `completed`，输出包含 `web_search_call` 的 `search` 与 `open_page` 动作，实际打开了 arXiv 页面并返回论文内容。项目自身的 `WebResearchAgent` 同样以 `responses_web_search` 模式完成搜索，找到 `Local Geometry Improves Explanation Robustness for Graph Neural Networks` 的 IJCAI 2026 页面；独立核验器确认标题、主会、日期 `2026-09-16` 和 PDF 均有效。
- 结论：DeepSeek 最近一次 5 篇运行的 `conference 0/3` 不是“模型不能联网”。其本地函数工具已经完成搜索，但在 3 轮/每轮工具预算内没有稳定返回可核验的合格会议落地页；报告还显示 KDD/WWW/VLDB/EMNLP 页面未命中允许主会或部分候选超出日期窗口。换用 LAYSO 原生 Responses 联网搜索后，会议检索链路已通过最小端到端测试。尚未用新供应商执行完整 `search --limit 5`，避免在能力探针后自动产生额外批量请求。

## 2026-09-27 静态页面增量导出核验

- `search`、兼容的 `run`/`summarize` 和 `build` 均调用 `gnn_digest.storage.export_site`；导出文件为 `site/data/papers.json`，前端 `site/app.js` 通过 `fetch('./data/papers.json')` 加载，因此本机完成检索后只要提交 `site/`，新论文就会进入 GitHub Pages 页面。`.github/workflows/pages.yml` 在 `site/**` 变化时部署。
- 修复 `tests/test_pipeline.py` 的静态导出回归夹具，新增测试确认新归档论文会出现在公开索引、状态/方法保留且 `full_text` 不会发布。`python -X utf8 -m unittest discover -s tests -q` 共 55 项通过；`node --check site/app.js`、`compileall`、`git diff --check` 均通过。
- 执行 `python -X utf8 run.py build` 后归档 94 篇、公开索引 92 篇（2 篇 `irrelevant` 按设计不展示），ID 集合一致；公开索引不含 `full_text`、`abstract` 或 `evidence`。本次 `data/search_results.json` 的 2 篇最新结果均能在 `site/data/papers.json` 找到。通过本地 HTTP 服务实测 `/` 与 `/data/papers.json` 均 HTTP 200。
- 当前只完成本地构建与验证；要更新线上 GitHub.io，需提交 `README.md`、`memory.md`、测试及之后检索生成的 `data/`、`site/` 变更并推送 `main`。此前 GitHub 凭据弹窗取消，远程可能仍未包含本地提交。

## 2026-09-27 GitHub 仓库迁移

- 按用户提供的新仓库地址，`origin` 已切换为规范地址 `https://github.com/Liujiachen1234567/Awesome-GNN.git`；旧账号仓库不再作为本地推送目标。
- 清除旧 GitHub 凭据缓存后，完整 `main` 分支已成功推送，远程 `main` 当前包含提交 `4214f24`。远程 Test pipeline 已通过。
- 新仓库的 Pages 地址为 `https://liujiachen1234567.github.io/Awesome-GNN/`。首次推送未触发 Pages（最后提交没有 `site/**` 改动），`site/index.html` 增加 canonical 链接后已触发工作流；通过 Pages API 启用 Actions 发布并手动 dispatch 后，`Publish site` 成功，页面首页和 `data/papers.json` 均 HTTP 200，公开数据为 92 篇。

## 2026-09-27 Responses 搜索超时调优

- 最近一次 `search --limit 5` 在 LAYSO `/responses` 第一轮约 130 秒后出现 `network/timeout failure`，没有返回任何 web-search action/citation；`data/papers.json` 归档仍为 94 篇。`/models` HTTP 200 且包含 `gpt-5.6-luna`，因此不是密钥、模型不存在或论文来源核验失败。
- 为降低复杂联网请求的上游耗时，本机 `.env` 的 `LLM_REASONING_EFFORT` 已改为 `low`，`config.json` 的 `search_agent.max_tool_calls_per_round` 已从 4 改为 2。此次只修改配置，未自动重跑搜索；用户可手动执行 `python -X utf8 run.py search --limit 5` 验证。

## 2026-09-29 Yundou 联网与浏览器方案核验

- 当前本机 `.env` 为 `https://yundou.ai/v1`、`gpt-5.6-sol`、`low`；密钥仍仅在被忽略的本机配置内，本记录不含密钥。
- 9月27日被聊天中断的检索实际已在后台完成（147.81秒）：三轮均有 completed 搜索动作，返回0/5。报告中的会议候选日期不足/超出14天窗口；唯一送去总结的 arXiv 候选被 `evidence must be 1-3 verbatim full-text spans` 拒绝。不能把0篇归因于API没有联网，也不能据此断言窗口内没有合格论文。
- 9月29日仅运行小规模探针，未再次启动批量检索：`GET /models` HTTP 200且包含当前模型；一次 `POST /responses`（web_search、required、low、store=false）HTTP 200，约7.61秒，返回 completed 的 search 和 open_page、引用及论文元数据。目标为IJCAI 2025的DGExplainer（/proceedings/2025/349）；API返回的标题、首作者、DOI、页码、PDF链接、摘要原句与浏览器原站内容逐项一致。这验证当前账号/模型路径可搜索并打开外部页面，不代表所有站点或严格配额都能成功。
- 本机内置浏览器从Google结果点击进入IJCAI原站成功；Python requests首次抽样访问IJCAI、ACL Anthology、arXiv、Crossref均HTTP 200。随后独立复读IJCAI时出现一次SSL EOF，未关闭TLS验证或绕过代理，采用已打开的浏览器页面核对；说明HTTP访问存在间歇性失败，不能宣称全网稳定可达。
- 探针与脱敏结果保存在被忽略的 `.local/probe_network_20260929.py`、`.local/network_probe_20260929.json`。本轮未改检索逻辑、归档或静态页面，未推送。API原生web_search与本机浏览器是不同执行路径：独立Python脚本若要使用浏览器，需显式接入工具执行循环，不能仅靠提示词取得本会话浏览器工具。
- 建议后续保持LLM多步工具调用：发现候选→原站/书目API核验→PDF全文→总结与证据验证→去重导出；本机HTTP为主、浏览器用于动态/失败页面。会议与arXiv可分别配置时间窗口以提高会议召回，但未经用户确认不改变现行14天窗口或来源配额。

## 2026-09-29 多步检索改造与最终3篇验收

- 用户已同意改造并实测。`config.json.search_windows`设置会议90天、arXiv14天；`agent.source_windows`将对应窗口同时交给模型和原站核验器，本地DeepSeek工具路径也分别使用两类窗口。新增`--conference-days`和`--arxiv-days`，优先级为专用参数 > 通用`--days` > 来源配置。旧`window`为外包区间，资格以`source_windows`为准；不改变来源范围、精确正式日期要求或奇数会议多一篇的配额。
- `search.agent.txt`与`search.request.txt`细化搜索→打开原站→缺字段补搜→独立核验。每轮工具目标恢复4次，为打开页面预留预算，Responses未发送`max_tool_calls`时仍只是提示词目标。反馈增加`stage`、`code`、`next_action`；缺日期/会议身份/全文过长/源不可达分开。标题纠正和临时网络失败按`retry_same_url`最多再核验一次，修复旧seen集合永久跳过同一URL的问题；不把目录或arXiv声称的录用当作会议核验。
- `gnn_digest/evidence.py`负责原文定位。初版只容忍空白排版差异，但真实模型仍频繁产生过长引文。因此最终`search`把完整正文连续分为最长180字符的编号片段，全部交给模型；模型选`evidence_ids`及`topic_evidence_ids`，程序解析真实编号并保存原文和字符偏移，不截断全文、不替模型写方法总结。保留旧引文兼容，拒绝改写、拼接及无效编号。`llm.py`记录字段级错误和修复历史，关键词数量/类型/长度也单独诊断。缓存版本已更新，旧全文/摘要归档不批量重算。
- 三次有界真实运行均为`python -X utf8 run.py search --limit 3`：第一版0/3（ACL缺精确日期，arXiv全文超过12万字符/HTTP错误）；定向补搜版0/3（能发现会议，关键词/引文格式未通过）。脱敏历史报告在gitignored `.local/search-repairs-first-report.json`和`.local/search-repairs-second-report.json`。最终编号证据版**3/3达标、退出0**，耗时93.92秒，2轮搜索，2篇会议+1篇arXiv，三篇均首次总结通过。
- 最终会议窗口2026-07-02至2026-09-29，arXiv窗口2026-09-16至2026-09-29。新增论文：IJCAI `/2026/302`，History Doesn’t Repeat, but Its Patterns Echo（2026-09-16）；IJCAI `/2026/310`，Beyond Homophily（2026-09-16）；arXiv `2609.35021`，Addressing Spatial Indistinguishability in Spatiotemporal Prediction via Optimal Transport-Guided Masking（v1 2026-09-28）。完整标题、方法和证据见`data/search_results.json`/`data/papers.json`。
- 验证：69项unittest通过，`node --check site/app.js`和Python编译通过；两份skill通过quick_validate（Windows用`python -X utf8`）。实际三篇无跨源重复，方法分别143/105/122字，各5关键词，证据及主题证据偏移与全文逐项一致。归档97篇，公开95篇（2篇历史irrelevant不展示）；本次3个ID均进入静态索引，公开记录无全文/证据，PDF链接一致。浏览器验证95篇/9张方法卡片、3/3配额提示、两篇会议搜索筛选与PDF优先跳转地址均正确。
- README、仓库skill和本机安装skill已同步。API仍为本机Yundou `gpt-5.6-sol`/`low`，密钥未改、未入库。此次未提交/推送，线上Pages尚未更新；本地预览服务启动在127.0.0.1:8000。`data/pipeline.lock`已释放。
- 剩余边界：独立Python命令未接入本机浏览器桥接，当前打开网页使用供应商Responses工具；12万字符/24MB/100页正文上限仍在，缺精确会议日期仍拒绝，不静默放宽。成功3篇只证明本次链路达标，不代表全网召回或所有站点稳定可达。

## 2026-09-29 仅保留三篇与页面精简

- 按用户明确要求，将`data/papers.json`从97条清理为本次新增的3篇（arXiv 2609.35021、IJCAI 2026/302、2026/310），移除94条旧归档记录；`site/data/papers.json`从95篇变为3篇，`last_run.json`及`search_results.json.report`的归档总数/状态同步为3篇ready。完整摘要、全文、证据与身份字段保留，不只是前端隐藏。删除前备份在被Git忽略的`.local/archive-before-prune-20260929T033108Z.json`，没有清除Git历史。
- `site/index.html`删除截图中的已生成卡片/数据来源/1–5×200三项统计、标题介绍、处理状态筛选和侧栏说明；保留已收录论文总数。`site/app.js`同步移除失效DOM引用、状态筛选及两条检索/配额提示，保留必要的错误提示。移动端来源/时间筛选从三列调整为两列，其他卡片样式和PDF优先链接不变。
- 浏览器曾缓存旧app.js，在新HTML上寻找已删除status控件导致加载失败；index.html现以内容哈希版本引用JS/CSS，刷新后恢复正常。以后修改JS/CSS应同步更新资源版本，避免新旧资源混用。
- 验证：69项unittest、`node --check`通过；HTTP返回文件与磁盘一致。浏览器桌面和390px手机视口均正常显示3张卡片，无横向溢出；来源conference筛选2篇，搜索Beyond Homophily为1篇，无匹配搜索显示空状态，最近7天为1篇，重置恢复3篇。截图中指定文字/控件均不再出现。
- 本轮不重新检索、不调用模型，以遵从只保留指定3篇的最新要求。未推送GitHub，线上仍是先前版本；本地预览仍在127.0.0.1:8000。

## 2026-09-29 TAG/OOD限定与151–200字Markdown方法总结

- 按用户新要求，主题白名单缩为`TAG`、`OOD`，满足任一即可。`verification.TOPICS`、搜索上下文和报告、固定需求及搜索/总结提示词、前端筛选与卡片标签均同步；方法关键词仍保留1至5个用于文本搜索，不再作为网页主题标签展示。TAG须有文本属性与图结构的实际方法，OOD须有明确分布偏移/跨域设定与方法或评测证据；背景提及、普通少样本、动态图或泛鲁棒性不单独成立。
- 新增`gnn_digest/summary_policy.py`，方法总结严格151至200个可见Unicode字符，去掉Markdown加粗标记及全部空白，中文、标点、英文字符与数字各计一个。保留原200上限；要求1至4处`**关键方法/模块/目标**`。提示词围绕具体问题、输入表示、模块连接、训练目标和下游推理写3至4句，建议170–190字符，综合全文、不靠空话凑字数。`llm.py`采用新校验及缓存版本，修复反馈同步；编号证据与全文大小限制保持。
- 新增`site/method-markdown.js`，仅用文本节点及`strong`渲染加粗，支持换行，不执行HTML/链接/代码。前端只显示有TAG/OOD主题的记录，更新JS/CSS内容哈希引用避免旧缓存。README、仓库skill和本机已安装skill同步规则；两份skill均通过quick_validate。
- 原3篇先备份到被忽略的`.local/archive-before-tag-ood-*.json`，用保存的全文逐篇重新调用模型。STOT（arXiv 2609.35021）判为irrelevant，保留本地归档但不导出页面；ATNSF（IJCAI 2026/302）依据测试时负样本分布偏移保留OOD，总结180字符；SCA-GPPT（IJCAI 2026/310）依据源/目标图频谱与属性变化保留OOD，总结167字符。三篇均首次校验通过；记录在`.local/tag-ood-refresh-report.json`。没有恢复此前删除的94篇。
- 按每次检索变更实测3篇的约定运行`python -X utf8 run.py search --limit 3`。耗时109.03秒，3轮完成，实际返回**2/3**：会议2/2、arXiv0/1。新增IJCAI 2026/286（Invariant Graph Representations for Continuous-Time Dynamic Graphs Under Distribution Shifts，OOD，193字符）与2026/328（CAMERA: Adapting to Semantic Camouflage in Unsupervised Text-Attributed Graph Fraud Detection，TAG，174字符），两篇正式日期均2026-09-16，均首次全文总结通过。arXiv未提交任何进入独立核验的候选；模型笔记报告检索结果v1早于窗口及部分搜索超时，不能据此断言窗口内不存在合格论文。未扩大14天窗口或以会议补足arXiv；停止原因为round_budget，结果和过程保存在data/search_results.json及data/last_run.json。
- 当前归档5条（4 ready、1 irrelevant），公开索引及实际页面4篇（TAG 1、OOD 3）。逐篇复核151–200字符、加粗数量、主题证据/方法证据匹配全文、新结果ID进入公开索引、无重复ID、公开记录不含全文/证据、PDF优先链接及资源哈希；pipeline.lock已释放。72项Python单测、3项JS渲染测试、JS语法、Python编译和git diff --check通过。浏览器实测TAG筛选1篇、OOD筛选3篇、CAMERA文本搜索1篇、重置4篇；桌面和390px手机无横向溢出，14处真实strong元素正常显示。
- API配置未改，密钥未进入项目数据、日志或Git。此次未提交或推送；当前效果在本地127.0.0.1:8000，线上Pages需后续推送才能更新。

## 2026-09-29 更新时间文案

- 页面顶部“最近运行”改为“最新更新时间：”，保留实际日期、时间与本地时间说明；同步刷新app.js资源哈希。JS语法检查通过，仅修改展示文案，未检索、未推送。

## 2026-09-29 卡片来源与状态文案精简

- 按用户三张截图修改`site/app.js`与`site/index.html`：删除ready卡片的“方法卡片已生成”，移除顶部“开放数据”入口；会议元信息合并为“2026 SIGIR”格式，不再附带出版日期及说明。优先使用`conference_year`，旧记录缺失时回退已存日期年份；有会议来源的跨源记录按会议显示。arXiv保留来源标签及日期，去掉“首次提交”。后台日期、排序和筛选口径保持不变。
- 更新`app.js`内容哈希`24cddf6ceb`避免旧缓存。JS语法检查通过；本地浏览器核对SIGIR为1张2026、3张2025卡片，arXiv显示纯日期，所删文案不再出现，无水平溢出，最终恢复全部来源和空搜索。验收时页面数据为113篇，本次仅修改展示，不运行检索、不改论文数据、不推送GitHub。

## 2026-09-29 100篇跨会议/年份批量检索（已完成）

- 用户将arXiv窗口扩为2026-01-01起，并要求覆盖允许会议已公布的2025/2026届，目标80会议+20arXiv，arXiv不足名额用会议补齐，仍不足则停止。`config.json.search_windows`改为固定起点，`bulk_search`配置有限覆盖与预算；CLI新增`--conference-since`、`--arxiv-since`，`--limit`允许至100。1–20篇兼容路径保留原比例，大于20启用`gnn_digest/bulk.py`。
- 批量先搜索arXiv（最多4批），确定20个名额实际完成数后转移缺口给会议；按15个允许会议及2026/2025逐项搜索，ICCV 2026不存在常规届而跳过，共29个会议/年份组合。默认每批最多12篇、候选20篇、最多2遍会议覆盖、总软预算7200秒和240篇全文处理。达到总数也继续首轮剩余会议的发现检查；后续不足则有限补搜，不强凑100。不新增ICLR/ECCV等不在硬白名单的会议；ACM MM从已有审计范围同步到硬白名单。
- 每批使用现有LLM工具检索与独立核验，`search_scope`限定来源/会议/年份，跨批按所有身份别名去重。arXiv PDF可由`fulltext_url`独立标题核验后供会议论文使用，不能作为会议身份凭据。`data/bulk_run.json`保存整体配额、每个范围的搜索动作、拒绝原因及未搜索范围，归档逐篇保存、每批导出静态索引；排他锁覆盖整个运行。
- 修复AAAI gzip元数据未解压的问题，按Technical Tracks识别主会；NeurIPS只接收主会URL，排除Creative AI等其他track；ACM/DOI受阻时使用出版方登记的Crossref proceedings-article，严格匹配标题、主会名并排除Companion/期刊。ICML可由官方节目页与OpenReview主会身份联合核验，取得论文PDF。宽窗口允许原站年/月精度而不补造日；官方ICML届次只显示“会议年份”。前端补充日期精度说明，更新资源哈希。
- 新增`tests/test_bulk.py`覆盖80/20回补、所有会议/年份计划、固定日期窗口、部分日期、跨批去重和检查点、AAAI/NeurIPS主会适配、Crossref排除错误类型；79项Python单测通过，JS语法、Python编译及两份skill验证通过。README、固定搜索提示词和两份skill同步新口径。
- 已于UTC 2026-09-29 05:22启动`python -X utf8 run.py search --limit 100`，运行日志为gitignored `.local/search-100.log`，原数据备份在`.local/before-bulk-*`。此处是运行中记录，不代表完成100篇；最终数量、来源分布与覆盖结果待运行结束补充。没有推送GitHub，API配置未改。
- 运行中修正：原OpenReview API对ICML返回403，官网自身JSON-LD却可核对CreativeWork题名、creditText=`ICML 年份`与datePublished。改用官网结构化证据，不绕过OpenReview防护；PDF不可读时按已核验完整题名精确查询公开arXiv API，再独立核验arXiv落地页，只补全文、不改变会议计数。KDD的DOI原本已通过Crossref核验，但额外directory_url触发旧的arXiv-only拒绝；现对已核验会议记录忽略该非必要提示，不降级为arXiv。Crossref HTML上标标题先去标记再精确归一，避免G2LoRA等格式差异误拒。
- 新增`--resume`：目标和窗口必须与bulk检查点一致，结果ID集合必须一致，累计原处理/时间预算，跳过已完成批次。AAAI 2026批完成后，在32篇（20 arXiv + 12 AAAI）完整检查点处停止原进程，确认进程退出后清理匹配的旧锁，标记ICML/KDD 2026两项修复重试，已用`search --limit 100 --resume`恢复；日志`.local/search-100-resume.log`。此前结果和报告另备份至`.local/bulk-*-before-repair.json`。82项测试通过，覆盖恢复不重复调用、目录提示不推翻会议核验、官网结构化记录与精确标题补全文。
- 2026届首轮覆盖后保存55篇检查点，再修复ACL原站`2026/7`未补零的月份格式（规范化为2026-07，不补日）。SIGMOD/PVLDB期刊式论文集需同时满足出版方DOI题名/出版信息与对应年正式会议名单中的精确题名，不能仅由期刊名/卷号推断会议。VLDB 2026名单实际位于`https://www.vldb.org/2026/program.html`，不使用会回到首页的`?papers-research`；PDF须匹配题名并提取本篇DOI，再核对节目表。只读实测UniTG（VLDB 2026）、GeoKGM（SIGMOD 2026）与AgentGL（ACL 2026）的来源核验均通过，主题是否符合仍由全文模型独立判断。
- 首轮后续会按剩余目标与未检查的会议/年份数量分配小批名额，先留出覆盖机会，第二遍才集中补足，避免排在前面的站点占满结果。达到100后的首遍剩余范围只发现/核验元数据，报告以`discovery_only`明确标记，不伪称生成了额外卡片。
- ACL续跑曾遇到PDF数学字体的UTF-16代理字符导致UTF-8哈希/写入失败，未覆盖原55篇检查点。`models.clean`将合法代理对无损合并为Unicode码点，孤立不可解码字形标为替换字符；后续全文/证据统一在规范化文本上定位。新增字符回归测试，84项测试通过。已再次`--resume`，日志`.local/search-100-resume3.log`，ACL已有3篇通过，实际批量任务仍在继续。异常时正常释放了锁，没有删除活动进程的锁。

### 最终完成与验收（以上为过程记录，以此处为准）

- 本轮已完成 **100/100**，其中会议 **80**、arXiv **20**，停止原因为`target_reached`，无配额缺口；arXiv v1窗口2026-01-01至2026-09-29，会议窗口2025-01-01至2026-09-29并限定2025/2026届。会议结果为2025届28篇、2026届52篇，来自13个会议；15个允许会议的29个有效会议/年份范围均已执行实际检索，未返回合格论文不等于不存在相关论文。
- 供应商一次网络超时后以缩小批次的有界重试恢复；修复续跑的轮次进展统计，按整个已记录轮次判断是否进入第二遍，避免跳过本进程开始前完成的批次时误判无进展。原检查点和成功结果始终保留。
- 补齐EMNLP主会`main/long/short`编号、WWW名称别名及PVLDB卷目录`__NEXT_DATA__`原始PDF解析。SIGMOD/PVLDB仍要求出版方元数据与官方会议名单共同核验；ICML节目页日期最终统一为`conference_program_publication`，页面标“官网公布”，不冒充正式论文集出版日期。已同步历史记录与前端资源内容哈希。
- 最终结果在`data/search_results.json`；完整批次轨迹在`data/bulk_run.json`及`data/last_run.json`；覆盖简表在`data/bulk_coverage_summary.json`；可读报告在`docs/last_bulk_search.md`。归档104条，公开索引103篇：本批100篇加批次之外保留的3篇，另有1条旧`irrelevant`归档不展示。没有恢复此前删除的无关历史库。
- 最终审计：100篇ID与身份别名去重，均符合TAG/OOD及来源/日期要求；方法总结实际155–200可见字符，加粗格式合格；410处证据偏移逐一匹配全文；100个结果ID均已进入公开索引，公开数据不含正文、摘要或证据。`data/`和`site/`未发现当前API密钥，`pipeline.lock`已释放。审计结果保存于gitignored `.local/final-bulk-validation.json`。
- 验证完成：86项Python测试、3项JS Markdown渲染测试、JS语法、Python编译及`git diff --check`通过。浏览器加载更多后显示103个不同标题、306处真实加粗；来源筛选arXiv20/会议83，主题TAG50/OOD63（可交叉），UniTG搜索与官方PDF链接正确。桌面与390px手机无横向溢出；搜索与筛选已复位，无误报配额或LLM连接状态。
- 本轮API配置未改变，未再次执行付费检索。代码、数据及本地页面已更新，**尚未提交或推送GitHub，线上Pages仍为旧版本**。后续新检索命令为`python -X utf8 run.py search --limit 100`；仅中断续跑时增加`--resume`。

## 2026-09-29 最新届次独立补漏审计（已完成本地导出）

- 用户扩大到 ICLR、LoG、ICDM 等相关会议，并要求按会议取最新公开届次（优先 2026，否则 2025）。本轮不使用原 100 篇配额搜索，参考 naganandy 文献库、官网目录和出版方元数据高召回筛选 TAG/OOD，核验完整正文并生成 151–200 字加粗方法总结。
- 有效范围见 `data/literature_audit_scope.json`；EMNLP 已改用 2026 MAIN 官方日程。LoG 最新录用名单未完整读到，暂不新增 2025；NeurIPS / ACM MM / ICDM 的 2026 公开集仍有待核实，2025 是有条件回退，不能将访问失败当作没有新论文。
- 参考目录 25 个索引、3,598 条记录；联合候选 3,440 条，其中符合最终届次 3,274 条，3,214 条成功题名初筛，60 条已有归档。补审修复数字批次缓存输入漂移，按真实成功 ID 并集统计，采用内容哈希缓存；EMNLP 2026 另核验 85 个图相关 MAIN 标题。
- 新增复用脚本：`scripts/audit_literature.py`、`import_literature_candidates.py`、`screen_literature_gaps.py`、`summarize_literature_candidates.py`、`publish_literature_audit.py`、`report_literature_audit.py`。原始记录/正文/历史错误缓存在 gitignored `.local/literature-audit/`。具体阶段见 `docs/latest_conference_coverage_audit.md` 和 `data/literature_pending.json`。
- 网络恢复探针会议官网和当前模型均 HTTP 200；历史 127 个总结请求失败中 121 个为 network/timeout failure。正在只对失败缓存进行有界恢复，不重复搜索和下载已取得正文。摘要请求连续失败停止；书目、全文和总结失败分别记录。
- 两篇已有 arXiv 论文 REFINE、Call Neighbours Yourself 已按官方 EMNLP 2026 MAIN 日程补会议归属，复用原有效全文总结，保持持久 ID，不作为新增论文计数。
- 扩充 `verification.py` 支持 ICLR 官方节目/论文集、ICDM/WSDM/NAACL/LoG 别名，依然排除 workshop；审计全文上限可显式设为 240000 字符，默认入口仍为 120000，不截断全文。严格 OOD 提示词排除仅训练客户端 Non-IID/仅相关工作提及的论文。
- 89 项 Python 测试、3 项 Markdown 渲染测试和 JS 语法通过，最终数据校验待完成。本轮未提交/推送；不得误称线上已更新。

### 2026-09-30 最终检查点

- 每个会议按最新可核验届次独立筛选；原有 113 篇公开记录保留。本轮新增 **188 篇**，`site/data/papers.json` 共 **301 篇**。192 条审计结果状态为 `ready`，其中 188 篇属于去重后新增；`data/literature_audit_results.json` 与持久归档身份一致。
- 联合候选 3,440 条，最终届次内 3,274 条；3,214 条成功题名初筛，其余 60 条已在原库。公开报告另列 423 条待处理候选，不能据此声称已收齐 TAG/OOD。LoG 2026 正式名单/轨道仍未完整核验；NeurIPS、ACM MM、ICDM 2026 的目录确认不充分，2025 回退是暂定；ECCV 2026 尚是来源缺口。VLDB 2026 仅接收官网 `res-N` 研究分会场题名，排除教程、演示和 workshop。
- 缓存全文有 28 篇总结请求失败、2 篇待总结；本次对 28 篇做有界重试，连续 3 批 `network/timeout failure` 后断路停止，未产生新总结。失败项保留在 `.local/literature-audit/`，不进入页面。另有 271 篇全文未解决、132 篇元数据未解决；这些状态不能当作无相关论文。
- `scripts/publish_literature_audit.py --final`、`report_literature_audit.py`、`validate_literature_export.py` 完成；校验确认 301 张卡片身份唯一、151–200 可见字符的方法总结及逐字全文证据有效，公开数据不含全文/证据。91 项 Python 测试、3 项 JS 渲染测试、JS 语法和 `git diff --check` 通过。浏览器实测本地页面显示 301 篇，TAG 筛选显示 161 篇，复位和 PDF 链接可用。
- 最终范围、逐会数量和未解决原因见 `docs/latest_conference_coverage_audit.md`，待处理清单见 `data/literature_pending.json`。本次仅更新本地数据和页面，**尚未提交或推送 GitHub**；线上 GitHub Pages 不会自动得到这 188 篇。

### 2026-09-30 旧仓库发布状态

- `origin` 已改回 `https://github.com/LiuJiaChen0x3f/Awesome-GNN.git`；本地 `main` 的 `da66446` 已提交 301 篇索引、页面改动和审计数据。`site/app.js` 的“最新更新时间”已去掉“本地时间”后缀，`site/index.html` 的 canonical 指向旧账号 Pages。
- 旧仓库 `main` 仍为 `adb55c2`，可正常快进；本机现有 GitHub 凭据属于另一个账号，推送返回 403。SSH 无可用公钥授权。不能称已推送或已上线。
- 2026-09-30 检查旧站 `data/papers.json` 仍为 92 篇、生成时间 2026-09-27；本地待发布索引为 301 篇、生成时间 2026-09-30。获得旧仓库写权限后推送 `main`，核对 Pages 工作流和线上数据，再更新本节状态。
