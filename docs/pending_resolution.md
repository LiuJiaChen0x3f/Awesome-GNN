# 待处理清单处理记录

> 本页保留 2026-09-30 第一轮处理快照。后续对剩余 301 条的最新补查结果见 [2026-10-01 arXiv 与出版方全文补查](arxiv_recovery_2026-10-01.md)；当前未解决条目以 `data/literature_pending.json` 为准。

核查时间：2026-09-30T15:16:18.134387+00:00。本轮原始待处理 423 条；已结案 122 条，剩余 301 条。

“结案”包括核验通过、全文判定不相关、确认不符现有轨道范围或已归档；不等于全部新增论文。

| 本轮原始候选的当前状态 | 数量 |
|---|---:|
| 按范围排除 | 46 |
| 全文待恢复 | 248 |
| 全文判断不符合 TAG/OOD 方法要求 | 36 |
| 书目/身份待核验 | 53 |
| 通过全文核验 | 40 |

当前本地页面共 340 篇；本轮之前为 301 篇，去重后净新增 39 篇。40 条候选通过核验不等于 40 篇唯一新增记录。结果已同步本地页面数据，本次未推送 GitHub。
验证：96 项 Python 测试、JS 语法及正式索引校验通过；隔离真实检索 3/3（会议 2、arXiv 1），隔离结果不计入本轮新增。

## 处理了什么

- 重试原有 28 篇完整正文的失败总结；对超长总结逐篇重写，继续检查 151–200 字、加粗方法名及逐字全文证据。
- 对可用书目缓存尝试 arXiv 官方网页精确题名补查和出版方 PDF；arXiv 镜像只提供全文，不替代会议录用证明。
- 从 NeurIPS 2025 官方主会议论文集按规范化精确标题找回候选的正式入口及正文。
- 缺少书目缓存的记录重新执行身份核验；访问失败、题名不一致、未找到正文均保留，不填造元数据。
- 从 ACL 官方元数据确认 Findings 和其他非主会轨道，不再将范围排除伪装为下载故障。
- 对超过常规 24 MB 限制的少量 PDF 使用本轮专用 64 MB 有界恢复，仍保留 100 页、240000 字符上限及题名检查；未更改生产抓取限制。

## 用户已确认的范围

1. 纳入正式归档的专题研究轨道及数据集/基准轨道，已落地 IJCAI AI and Health、AI and Social Good、AI4Tech、NeurIPS Datasets and Benchmarks；仍排除 workshop、演示、博士生论坛、综述。
2. 继续排除 Findings。本轮无需再次确认范围；技术访问失败保留待恢复。

### 已核对官方轨道的候选及处理结果

| 会议 | 官方轨道 | 候选论文 | 结果 |
|---|---|---|---|
| 2026 IJCAI | AI and Social Good | [Domain-Informed Graph Neural Networks for Climate Factor Forecasting to Support Sustainable Crop Management](https://www.ijcai.org//proceedings/2026/827) | 全文判断不符合 TAG/OOD 方法要求 |
| 2026 IJCAI | AI and Health | [LLM as Clinical Graph Structure Refiner: Enhancing Representation Learning in EEG Seizure Diagnosis](https://www.ijcai.org//proceedings/2026/753) | 全文判断不符合 TAG/OOD 方法要求 |
| 2026 IJCAI | AI and Social Good | [LLM-Enhanced Knowledge and Learning Path Understanding for Graph-based Educational Recommendation](https://www.ijcai.org//proceedings/2026/813) | 通过全文核验 |
| 2026 IJCAI | AI and Health | [LLM-Guided Monte Carlo Tree Search over Knowledge Graphs: Composing Mechanistic Explanations for DrugDisease Pairs](https://www.ijcai.org//proceedings/2026/751) | 通过全文核验 |
| 2026 IJCAI | AI4Tech: AI Enabling Technologies | [Leveraging Implicit Contexts via LLMGraph Fusion for Temporal Knowledge Graph Reasoning](https://www.ijcai.org//proceedings/2026/727) | 通过全文核验 |
| 2026 IJCAI | AI and Health | [Structure-Aware Contrastive Learning for Biomedical Embeddings: Bridging the Gap Between HPO and Clinical Literature](https://www.ijcai.org//proceedings/2026/760) | 通过全文核验 |
| 2026 IJCAI | AI and Social Good | [Temporal Motif-aware Graph Test-time Adaptation for OOD Blockchain Anomaly Detection](https://www.ijcai.org//proceedings/2026/802) | 通过全文核验 |
| 2025 NeurIPS | Datasets and Benchmarks | [BOOM: Benchmarking Out-Of-distribution Molecular Property Predictions of Machine Learning Models](https://papers.nips.cc/paper_files/paper/2025/hash/b94263f7f98c9766ea9a09761ddd88ee-Abstract-Datasets_and_Benchmarks_Track.html) | 全文判断不符合 TAG/OOD 方法要求 |
| 2025 NeurIPS | Datasets and Benchmarks | [MiNT: Multi-Network Transfer Benchmark for Temporal Graph Learning](https://papers.nips.cc/paper_files/paper/2025/hash/c5548168cb7324f714365a971dfe76d1-Abstract-Datasets_and_Benchmarks_Track.html) | 通过全文核验 |
| 2025 NeurIPS | Datasets and Benchmarks | [ModuLM: Enabling Modular and Multimodal Molecular Relational Learning with Large Language Models](https://papers.nips.cc/paper_files/paper/2025/hash/9d71f47d4f1d240b02bb173936e5bf01-Abstract-Datasets_and_Benchmarks_Track.html) | 全文判断不符合 TAG/OOD 方法要求 |
| 2025 NeurIPS | Datasets and Benchmarks | [RDB2G-Bench: A Comprehensive Benchmark for Automatic Graph Modeling of Relational Databases](https://papers.nips.cc/paper_files/paper/2025/hash/b0cbac3acd497f5ab2b2ca83c6c6bc56-Abstract-Datasets_and_Benchmarks_Track.html) | 全文判断不符合 TAG/OOD 方法要求 |
| 2025 NeurIPS | Datasets and Benchmarks | [RoFt-Mol: Benchmarking Robust Fine-tuning with Molecular Graph Foundation Models](https://papers.nips.cc/paper_files/paper/2025/hash/013acf7d59f4333131fc8581e86148b1-Abstract-Datasets_and_Benchmarks_Track.html) | 通过全文核验 |
| 2025 NeurIPS | Datasets and Benchmarks | [Semantic-KG: Using Knowledge Graphs to Construct Benchmarks for Measuring Semantic Similarity](https://papers.nips.cc/paper_files/paper/2025/hash/26cf2796210e804ad554b8734ce0760b-Abstract-Datasets_and_Benchmarks_Track.html) | 全文判断不符合 TAG/OOD 方法要求 |
| 2025 NeurIPS | Datasets and Benchmarks | [UniHG: A Large-scale Universal Heterogeneous Graph Dataset and Benchmark for Representation Learning and Cross-Domain Transferring](https://papers.nips.cc/paper_files/paper/2025/hash/1568882ba1a50316e87852542523739c-Abstract-Datasets_and_Benchmarks_Track.html) | 通过全文核验 |
| 2025 NeurIPS | Datasets and Benchmarks | [When No Paths Lead to Rome: Benchmarking Systematic Neural Relational Reasoning](https://papers.nips.cc/paper_files/paper/2025/hash/167856a2bb094d44872c4a992bad49d0-Abstract-Datasets_and_Benchmarks_Track.html) | 全文判断不符合 TAG/OOD 方法要求 |

### Findings 候选（27 条）

- [A Graph Talks, But Who’s Listening? Rethinking Evaluations for Graph-Language Models](https://aclanthology.org/2026.findings-acl.1624/)
- [A ny G raph: Graph Foundation Model in the Wild](https://aclanthology.org/2026.findings-acl.44/)
- [Analyze Like a Venture Capitalist: Information-Gain and Knowledge Enhanced Graph Reasoning for Startup Success Prediction](https://aclanthology.org/2026.findings-acl.1555/)
- [Anonpsy: A Graph-Based Framework for Structure-Preserving De-identification of Psychiatric Narratives](https://aclanthology.org/2026.findings-acl.963/)
- [CVRH : Cross-modal Variational Role Hypergraph Network via Semantic Enhancement for Multi-modal Event Argument Extraction](https://aclanthology.org/2026.findings-acl.978/)
- [Colorful Talks with Graphs: Human-Interpretable Graph Encodings for Large Language Models](https://aclanthology.org/2026.findings-acl.2049/)
- [Critic Rule Induction: Improving Temporal Knowledge Graph Forecasting with Generator-Critic Language Models](https://aclanthology.org/2026.findings-acl.1471/)
- [EHRAG : Bridging Semantic Gaps in Lightweight G raph RAG via Hybrid Hypergraph Construction and Retrieval](https://aclanthology.org/2026.findings-acl.1233/)
- [Exploring Graph Learning Tasks with Pure LLM s: A Comprehensive Benchmark and Investigation](https://aclanthology.org/2026.findings-acl.389/)
- [G a L a: Hypergraph-Guided Visual Language Models for Procedural Planning](https://aclanthology.org/2026.findings-acl.980/)
- [GOB ench: Stage-Wise Diagnostics and the Visual Paradox in Multimodal Graph Optimization](https://aclanthology.org/2026.findings-acl.306/)
- [Generalizable LLM Learning of Graph Synthetic Data with Post-training Alignment](https://aclanthology.org/2026.findings-acl.586/)
- [Investigating Links between Illicit Massage Businesses through Natural Language Processing and Graph Machine Learning](https://aclanthology.org/2026.findings-acl.1702/)
- [K- GIP : Diagnosing Logical Fractures in Large Vision-Language Models via Verification Scene Graphs and Sequential Pruning](https://aclanthology.org/2026.findings-acl.497/)
- [LEDGER : Scaling Agentic Document Editing with Dependency-aware Graph Retrieval](https://aclanthology.org/2026.findings-acl.515/)
- [MAKI : Multi-layer Aligned Knowledge Injection for Structure-aware Knowledge Graph Completion with Large Language Models](https://aclanthology.org/2026.findings-acl.1423/)
- [Not All Modalities at Once: Dynamic Dropout and Bidirectional Fusion for Robust Multi-modal Knowledge Graph Completion](https://aclanthology.org/2026.findings-acl.890/)
- [P anorama RAG : Enabling Consistent Global Topic Awareness in Graph-Based RAG](https://aclanthology.org/2026.findings-acl.1998/)
- [Query-Aware Graph Attention for Precise Subgraph Retrieval in Knowledge-Augmented Reasoning](https://aclanthology.org/2026.findings-acl.398/)
- [SGG -R 3 : From Next-Token Prediction to End-to-End Unbiased Scene Graph Generation](https://aclanthology.org/2026.findings-acl.992/)
- [See or Say Graphs: Agent-Driven Scalable Graph Understanding with Vision-Language Models](https://aclanthology.org/2026.findings-acl.2066/)
- [Structure-Aware Zero-Shot Relational Learning for Knowledge Graphs without External Knowledge](https://aclanthology.org/2026.findings-acl.941/)
- [T ag RAG : Tag-guided Hierarchical Knowledge Graph Retrieval-Augmented Generation](https://aclanthology.org/2026.findings-acl.321/)
- [T opo RAG : Graph-based RAG via Topology-aware Approximate Nearest Neighbor Search](https://aclanthology.org/2026.findings-acl.1703/)
- [TRUST : Towards Robust Social Bot Detection via Uncertainty-Guided Pseudo-Labeling and Graph Structure Purification](https://aclanthology.org/2026.findings-acl.1575/)
- [UCGR ec: User-Centric Graph Learning for LLM -based Sequential Recommendation](https://aclanthology.org/2026.findings-acl.175/)
- [Z oom RAG : Hierarchical Random-walk Zooming across Multi-scale Information Graphs for Fast and Accurate RAG](https://aclanthology.org/2026.findings-acl.1643/)

## 无需用户确认的技术缺口

- 出版方/arXiv 限流或拒绝访问、缺少可定位全文、PDF 无法完整提取：保留待恢复，不能降级为摘要总结。
- 缺官方书目、题名或主会身份不一致：保留待核验，不要求用户凭猜测批准录用身份。
- LoG 2026 官方 CfP 的决定日期已过，但 Program 为占位链接，尚未取得可核验完整录用名单；NeurIPS 2026 虚拟页面明确提示尚未开放。ACM MM 完整目录未取得，ICDM 站点 TLS 失败。都不能宣称已覆盖。

## 本轮通过全文核验的条目

- 2026 ACL：Evolving Beyond Snapshots: Harmonizing Structure and Sequence via Entity State Tuning for Temporal Knowledge Graph Forecasting
- 2026 EMNLP：CORTEX: High-Quality Cross-Domain Organization of Web-Scale Corpora through Ontological Corpus Graph
- 2026 EMNLP：HiTeC: Hierarchical Contrastive Learning on Text-Attributed Hypergraph with Semantic-Aware Augmentation
- 2026 EMNLP：LLM as GNN: Graph Vocabulary Learning for Text-Attributed Graph Foundation Models
- 2026 EMNLP：One Model, Many Graphs: Learning over Attributed Graphs across Heterogeneous Modalities with Vision-Language Models
- 2026 EMNLP：ReGraP-LLaVA: Reasoning enabled Graph-based Personalized Large Language and Vision Assistant
- 2026 ICLR：SAGA: Structural Aggregation Guided Alignment with Dynamic View and Neighborhood Order Selection for Multiview Graph Domain Adaptation
- 2025 NeurIPS：GraphKeeper: Graph Domain-Incremental Learning via Knowledge Disentanglement and Preservation
- 2026 CVPR：M^3KG-RAG: Multi-hop Multimodal Knowledge Graph-enhanced Retrieval-Augmented Generation
- 2026 ICML：Graph-R1: Towards Agentic GraphRAG Framework via End-to-end Reinforcement Learning
- 2026 IJCAI：D²G-TO: Task-aware and OOD-guided Discrete Graph Diffusion for Robust CNS Drug Discovery
- 2026 IJCAI：LLM-Enhanced Knowledge and Learning Path Understanding for Graph-based Educational Recommendation
- 2026 IJCAI：LLM-Guided Monte Carlo Tree Search over Knowledge Graphs: Composing Mechanistic Explanations for DrugDisease Pairs
- 2026 IJCAI：Leveraging Implicit Contexts via LLMGraph Fusion for Temporal Knowledge Graph Reasoning
- 2026 IJCAI：Structure-Aware Contrastive Learning for Biomedical Embeddings: Bridging the Gap Between HPO and Clinical Literature
- 2026 IJCAI：Temporal Motif-aware Graph Test-time Adaptation for OOD Blockchain Anomaly Detection
- 2026 KDD：Learning and Editing Universal Graph Prompt Tuning via Reinforcement Learning
- 2025 NeurIPS：Equilibrium Policy Generalization: A Reinforcement Learning Framework for Cross-Graph Zero-Shot Generalization in Pursuit-Evasion Games
- 2025 NeurIPS：ExGra-Med: Extended Context Graph Alignment for Medical Vision-Language Models
- 2025 NeurIPS：MiNT: Multi-Network Transfer Benchmark for Temporal Graph Learning
- 2025 NeurIPS：RoFt-Mol: Benchmarking Robust Fine-tuning with Molecular Graph Foundation Models
- 2025 NeurIPS：UniHG: A Large-scale Universal Heterogeneous Graph Dataset and Benchmark for Representation Learning and Cross-Domain Transferring
- 2026 VLDB：QA-GraphRAG: Query-Adaptive Plug-and-Play Retrieval Integration for
                  Graph-based Retrieval-Augmented Generation
- 2026 AAAI：GraphTextack: A Realistic Black-Box Node Injection Attack on LLM-Enhanced GNNs
- 2026 ACL：LegalGraphRAG: Multi-Agent Graph Retrieval-Augmented Generation for Reliable Legal Reasoning
- 2025 ICCV：Taming the Untamed: Graph-Based Knowledge Retrieval and Reasoning for MLLMs to Conquer the Unknown
- 2026 ICLR：A Brain Graph Foundation Model: Pre-Training and Prompt-Tuning across Broad Atlases and Disorders
- 2026 ICLR：Flock: A Knowledge Graph Foundation Model via Learning on Random Walks
- 2026 ICLR：G-reasoner: Foundation Models for Unified Reasoning over Graph-structured Knowledge
- 2026 ICLR：HGNet: Scalable Foundation Model for Automated Knowledge Graph Generation from Scientific Literature
- 2026 ICML：Graph Neural Networks Are Not Continuous Across Graph Resolutions
- 2026 KDD：MemGraphRAG: Memory-based Multi-Agent System for Graph Retrieval-Augmented Generation
- 2025 NeurIPS：Enhanced Expert Merging for Mixture-of-Experts in Graph Foundation Models
- 2025 NeurIPS：GFM-RAG: Graph Foundation Model for Retrieval Augmented Generation
- 2025 NeurIPS：GRAVER: Generative Graph Vocabularies for Robust Graph Foundation Models Fine-tuning
- 2025 NeurIPS：On Transferring Transferability: Towards a Theory for Size Generalization
- 2025 NeurIPS：One Prompt Fits All: Universal Graph Adaptation for Pretrained Models
- 2025 NeurIPS：One for All: Universal Topological Primitive Transfer for Graph Structure Learning
- 2025 NeurIPS：Refining Norms: A Post-hoc Framework for OOD Detection in Graph Neural Networks
- 2025 NeurIPS：Towards Graph Foundation Models: Training on Knowledge Graphs Enables Transferability to General Graphs

可复核明细：`data/literature_pending_resolution.json`；剩余队列：`data/literature_pending.json`。原始缓存及每次重试前状态保存在本地 `.local/literature-audit/`，不上传全文缓存或密钥。
