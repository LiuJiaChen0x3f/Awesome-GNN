# arXiv 与出版方全文补查记录

更新：2026-10-01T04:43:04.390061+00:00。本轮从 **301 条**待处理候选开始，结案 **135 条**，仍待处理 **166 条**。

去重后净新增 **61 篇**，本地页面 **401 篇**。本轮未推送 GitHub。

| 当前处理结果 | 候选数 |
|---|---:|
| 重复线索，已收录 | 2 |
| 出版物不符会议范围 | 2 |
| 全文未取得/无法完整提取 | 138 |
| 不符合 TAG/OOD 新方法要求 | 69 |
| 会议书目/身份仍未核验 | 28 |
| 全文核验与主题复核通过 | 62 |

## 检索与核验

- 第一轮联网检索覆盖 301/301 条，每条有结果或未找到说明；对其中 23 条明确 TAG/OOD 题名做第二轮作者、简称、标题片段与项目页检索。
- arXiv 官方 HTML 搜索出现 429 后暂停该路线，继续核验已取得的具体链接；请求失败不等于论文不存在。官方 HTML 请求状态及模型搜索动作计数见 JSON 报告。
- 默认以独立读取的完整题名及作者确认同一篇论文；作者姓名统一“姓, 名”和“名 姓”格式。改名版本须有项目/出版方页面将原题名与 arXiv 链接明确关联，保留来源快照。
- 会议论文使用 arXiv 仅补正文，不受独立 arXiv 收录的两个月窗口限制，也不借预印本声明绕过会议身份核验。
- 从 ICML 2026 的 PMLR 306 官方目录逐篇核对题名，并仅下载官方详情页明确链接的 mlresearch/v306 出版方 PDF，恢复 38 条全文。没有把任意 GitHub PDF 视为官方论文。
- 完整正文先生成方法卡片，再接受独立全文主题复核；每张新增卡片都需要具体文本属性与图结构结合，或明确图学习训练/测试分布变化及对应方法证据。仅使用 LLM/KG、一般泛化、异常检测或客户端 Non-IID 不够。
- 如初审多贴 OOD，复核可保留有证据的 TAG 并重写方法卡片；不相关论文排除，证据不确定或复核失败的记录不发布。总结继续要求 151–200 字、1–4 处方法加粗、1–5 个内部关键词及可定位全文证据。

## 新增论文

| 会议 | 主题 | 论文 |
|---|---|---|
| 2026 KDD | OOD | [Node4All: Learning Node Representation Beyond Datasets](https://arxiv.org/pdf/2607.17272) |
| 2026 KDD | OOD | [Unified Multi-Domain Graph Pre-training for Homogeneous and Heterogeneous Graphs via Domain-Specific Expert Encoding](https://arxiv.org/pdf/2602.13075) |
| 2026 KDD | OOD | [Generalizing GNNs with Tokenized Mixture of Experts](https://arxiv.org/pdf/2602.09258) |
| 2026 KDD | OOD | [USBD: Universal Structural Basis Distillation for Source-Free Graph Domain Adaptation](https://arxiv.org/pdf/2602.08431) |
| 2026 KDD | TAG / OOD | [H4G: Unlocking Faithful Inference for Zero-Shot Graph Learning in Hyperbolic Space](https://arxiv.org/pdf/2510.12094) |
| 2026 KDD | TAG | [CausalPOI: Spatio-Temporal Graph-Based Causal Modeling for Cold-Start POI Check-in Forecasting](https://arxiv.org/pdf/2606.05413) |
| 2026 SIGIR | TAG | [DCGL: Dual-Channel Graph Learning with Large Language Models for Knowledge-Aware Recommendation](https://arxiv.org/pdf/2605.07314) |
| 2026 ICML | TAG | [Bridging Structure and Semantics: Uncertainty-Modulated Dual-Path Diffusion for Robust Text-Attributed Graph Learning](https://raw.githubusercontent.com/mlresearch/v306/main/assets/yu26ab/yu26ab.pdf) |
| 2026 ICML | TAG | [From Retrieval to Translation: Translating Query into Graph-level Clues for Retrieval-Augmented Generation](https://raw.githubusercontent.com/mlresearch/v306/main/assets/liu26fy/liu26fy.pdf) |
| 2026 ICML | TAG | [$G^2$-Reader: Dual Evolving Graphs for Multimodal Document QA](https://arxiv.org/pdf/2601.22055) |
| 2026 ICML | OOD | [Rethinking GNNs and Missing Features: Challenges, Evaluation and a Robust Solution](https://arxiv.org/pdf/2601.04855) |
| 2026 ICML | OOD | [Subspace-Aware Feature Reshaping for Open-Set Graph Class-Incremental Learning](https://raw.githubusercontent.com/mlresearch/v306/main/assets/zhang26jd/zhang26jd.pdf) |
| 2026 ICML | OOD | [Uncertainty-Constrained Trustworthiness for Graph Learning](https://raw.githubusercontent.com/mlresearch/v306/main/assets/zhang26ch/zhang26ch.pdf) |
| 2026 ICML | TAG | [Weaving Graph over Tokens: Contextualizing Structured Sequences for LLMs](https://raw.githubusercontent.com/mlresearch/v306/main/assets/chen26gm/chen26gm.pdf) |
| 2026 ICML | OOD | [Size Transferability of Graph Convolutional Networks across Sparsity: A Generalized Graphon Perspective](https://raw.githubusercontent.com/mlresearch/v306/main/assets/shu26a/shu26a.pdf) |
| 2026 ICML | OOD | [CELL: A Causal Perspective for Fairness-aware Graph Adaptation](https://raw.githubusercontent.com/mlresearch/v306/main/assets/li26gu/li26gu.pdf) |
| 2026 ICML | OOD | [From Distribution to Geometry: Stable Graph Generalization via Invariant Barycenters](https://raw.githubusercontent.com/mlresearch/v306/main/assets/du26o/du26o.pdf) |
| 2026 ICML | OOD | [COPF: An Online Framework for Deployment-Stable Counterfactual Fairness in Evolving Graphs](https://raw.githubusercontent.com/mlresearch/v306/main/assets/li26kb/li26kb.pdf) |
| 2026 ICML | TAG / OOD | [A Graph Foundation Model with Cross-Modal Alignment and Modality-Aware Expert Fusion for Multi-Modal Graphs](https://raw.githubusercontent.com/mlresearch/v306/main/assets/he26at/he26at.pdf) |
| 2026 ICML | OOD | [Progressive Graph Structure Adjustment for Homophily Shift Adaptation](https://raw.githubusercontent.com/mlresearch/v306/main/assets/wen26j/wen26j.pdf) |
| 2026 ICML | TAG | [LECTOR: Joint Optimization of Scientific Reasoning Graphs and Introduction Generation](https://raw.githubusercontent.com/mlresearch/v306/main/assets/xiao26s/xiao26s.pdf) |
| 2026 ICML | OOD | [Rethinking Feature Alignment in Generalist Graph Anomaly Detection: A Relational Fingerprint-based Approach](https://arxiv.org/pdf/2605.25429) |
| 2026 ICML | TAG | [CCLRec: Consensus-driven Contrastive Learning for LLM-enhanced Graph Recommendation](https://raw.githubusercontent.com/mlresearch/v306/main/assets/guo26p/guo26p.pdf) |
| 2026 ICML | TAG | [HInT: Hypergraph Infusion at the Structural Layers Improves Table Understanding](https://raw.githubusercontent.com/mlresearch/v306/main/assets/lee26p/lee26p.pdf) |
| 2026 ICML | OOD | [CLINIC: Towards High-quality Graph Out-Of-Distribution Detection](https://raw.githubusercontent.com/mlresearch/v306/main/assets/wang26kt/wang26kt.pdf) |
| 2026 ICML | OOD | [Generalist Graph Anomaly Detection via Prototype-Based Distillation](https://arxiv.org/pdf/2605.26857) |
| 2026 ICML | OOD | [Adaptive Recurrent Message Passing for Test Time Computing on Graphs](https://arxiv.org/pdf/2606.22462) |
| 2026 ICML | OOD | [View Space: Learning Representation across Arbitrary Graphs](https://raw.githubusercontent.com/mlresearch/v306/main/assets/lee26ah/lee26ah.pdf) |
| 2026 ICML | OOD | [X-EviProbe: Post-hoc Parameter-Free Evidential Uncertainty Quantification for Frozen Graph Neural Networks](https://raw.githubusercontent.com/mlresearch/v306/main/assets/guo26ac/guo26ac.pdf) |
| 2026 ICML | TAG / OOD | [Enhancing LLMs for Graph Tasks via Graph-aware LoRA Generation](https://arxiv.org/pdf/2606.22429) |
| 2026 ICML | TAG | [Beyond Explicit Edges: Robust Reasoning over Noisy and Sparse Knowledge Graphs](https://arxiv.org/pdf/2603.14006) |
| 2026 ICML | TAG / OOD | [When LLMs Encounter Open-world Graph Learning: A Fresh View on Unlabeled Data Uncertainty](https://raw.githubusercontent.com/mlresearch/v306/main/assets/wen26e/wen26e.pdf) |
| 2026 ICDE | TAG | [AGRAG: Advanced Graph-Based Retrieval-Augmented Generation for LLMs](https://arxiv.org/pdf/2511.05549) |
| 2026 WWW | OOD | [VecFormer: Towards Efficient and Generalizable Graph Transformer with Graph Token Attention](https://arxiv.org/pdf/2602.19622) |
| 2026 WWW | TAG | [Detecting Miscitation on the Scholarly Web through LLM-Augmented Text-Rich Graph Learning](https://arxiv.org/pdf/2603.12290) |
| 2026 WWW | TAG | [VL-KGE: Vision–Language Models Meet Knowledge Graph Embeddings](https://arxiv.org/pdf/2603.02435) |
| 2026 WWW | OOD | [LEDA: Latent Semantic Distribution Alignment for Multi-domain Graph Pre-training](https://arxiv.org/pdf/2602.22660) |
| 2026 WWW | TAG | [Unveiling the Vulnerability of Graph-LLMs: An Interpretable Multi-Dimensional Adversarial Attack on TAGs](https://arxiv.org/pdf/2510.12233) |
| 2026 WWW | TAG | [Toward Graph-Tokenizing Large Language Models with Reconstructive Graph Instruction Tuning](https://arxiv.org/pdf/2603.01385) |
| 2026 WSDM | TAG | [Prompt Tuning without Labeled Samples for Zero-Shot Node Classification in Text-Attributed Graphs](https://arxiv.org/pdf/2601.03793) |
| 2026 EMNLP | TAG | [Cognition on Graph: Navigating Massive Knowledge Space via Cognitive Cycles and Bidirectional Graph-Text Synergy](https://arxiv.org/pdf/2609.12791) |
| 2026 EMNLP | TAG | [PGMem: Tightly Coupled Persona–Memory Graph for Lifelong Personalized Agents](https://arxiv.org/pdf/2608.01708) |
| 2026 EMNLP | TAG | [PunGraph: Retrieval-Enhanced Phonetic-Semantic Graph Reasoning for Pun Understanding](https://arxiv.org/pdf/2609.16557) |
| 2026 EMNLP | TAG | [Graph2Counsel: Clinically Grounded Synthetic Counseling Dialogue Generation from Client Psychological Graphs](https://arxiv.org/pdf/2604.20382) |
| 2026 EMNLP | TAG | [Athena: Vulnerability-Affected Library Identification via Knowledge Graph Completion](https://arxiv.org/pdf/2609.01187) |
| 2026 EMNLP | TAG | [Not All or None: Dynamic Construction of Target-aware Memory Graph for Conversational Stance Detection](https://arxiv.org/pdf/2608.29066) |
| 2026 EMNLP | TAG | [SAGE: Semantic Attribute Graphs for Multi-Entity Visual Retrieval](https://arxiv.org/pdf/2609.04255) |
| 2026 EMNLP | TAG | [GSEM: Graph-based Self-Evolving Memory for Experience Augmented Clinical Reasoning](https://arxiv.org/pdf/2603.22096) |
| 2026 EMNLP | TAG | [H²Table: Hierarchical Hypergraph-Enhanced Large Language Models for Complex Table Reasoning](https://arxiv.org/pdf/2609.01216) |
| 2026 EMNLP | TAG | [GraphLit: Learning Text-Enriched Dynamic Character Network Representations for Literary Study](https://arxiv.org/pdf/2605.28643) |
| 2026 EMNLP | TAG | [HyperProve: Answer-Guided Hypergraph Expansion for Multi-Hop Question Answering](https://arxiv.org/pdf/2609.13768) |
| 2026 EMNLP | TAG | [MemDreamer: Decoupling Perception and Reasoning for Long Video Understanding via Agentic Hierarchical Graph Memory](https://arxiv.org/pdf/2606.07512) |
| 2026 EMNLP | TAG | [Time is Not a Label: Continuous Phase Rotation for Temporal Knowledge Graphs and Agentic Memory](https://arxiv.org/pdf/2604.11544) |
| 2026 EMNLP | TAG | [Beyond Linearization: Attributed Table Graphs for Table Reasoning](https://arxiv.org/pdf/2601.08444) |
| 2026 EMNLP | TAG | [TDGNet: Hallucination Detection in Diffusion Language Models via Temporal Dynamic Graphs](https://arxiv.org/pdf/2602.08048) |
| 2026 EMNLP | TAG | [Graph-of-Skills: Dependency-Aware Structural Retrieval for Massive Agent Skills](https://arxiv.org/pdf/2604.05333) |
| 2026 EMNLP | TAG | [GraphProfiler: Source-Linked Sensitive Attribute Inference via Personal Knowledge Graphs](https://arxiv.org/pdf/2609.12448) |
| 2026 EMNLP | TAG | [Import What You Need: Learning When and How to Augment EHR Graphs with External Knowledge](https://arxiv.org/pdf/2609.01839) |
| 2026 EMNLP | OOD | [HyperGVL: Benchmarking and Improving Large Vision-Language Models in Hypergraph Understanding and Reasoning](https://arxiv.org/pdf/2604.15648) |
| 2025 ICDM | OOD | [Test-Time GNN Model Evaluation on Dynamic Graphs](https://arxiv.org/pdf/2509.23816) |
| 2025 ACM MM | OOD | [Towards Effective Open-set Graph Class-incremental Learning](https://arxiv.org/pdf/2507.17687) |

## 仍未完成的内容

仍未找到可读取全文或可靠会议元数据的候选继续保留。检索未命中、下载失败不能证明论文不存在；也不根据题名把它们宣布为相关论文。详细错误见 `data/literature_pending.json`，本轮逐条结果见 `data/arxiv_recovery_report.json`。

用户已确认的范围保持不变：纳入正式归档的专题研究/数据集轨道，继续排除 Findings 和 workshop。本轮没有新增加需要用户确认的范围问题。
