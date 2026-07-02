# PlotPilot (墨枢) vs StoryForge2 — 深度对比报告

> 比较对象：`/Users/longsa/Codes/plotPilot`（本文档所在项目）vs `/Users/longsa/Codes/storyForge2`
>
> 比较维度：项目结构、核心逻辑、技术栈与依赖、潜在风险与优势

---

## 一、项目结构对比

### 1.1 量化对比

| 维度 | PlotPilot | StoryForge2 |
|---|---|---|
| Python 总代码量 | **~205K LOC** | **~30K LOC** |
| 测试代码量 | ~42K LOC（338 个测试文件） | ~5K LOC（71 个测试文件） |
| 生产代码 | ~163K LOC | ~25K LOC |
| Python 源文件 | 1234 | 99 |
| 前端源文件 | 233（.vue/.ts） | 116（.tsx/.ts） |
| 架构范式 | **DDD 四层 + 独立引擎内核** | **能力链 / OS 化模块** |
| 主仓库文档 | ARCHITECTURE.md / README / CONTRIBUTORS | 仅 v1.0 设计稿（CLAUDE.md 仍称"尚未编码"） |
| CI/CD | `.github/workflows` 存在 | 无 .github |
| LICENSE | 完整（10KB） | 无 |

### 1.2 目录形态

**PlotPilot** 采用经典 DDD 分层 + 内核隔离：

```
domain/          17 个聚合根（novel / bible / character / cast / worldbuilding /
                 structure / knowledge / evolution / memory / prop / engine / ai / shared）
application/     34 个用例服务
engine/          独立运行时内核（runtime / pipeline / core / examples）
infrastructure/  替换式实现（ai/providers、persistence、json_stream、export）
interfaces/api/v1  按子域拆分的 REST API
```

每个 domain 聚合有独立的 entity / value object / repository 接口；application 用例通过 DI 容器（`interfaces/runtime.py`）注入；engine 是独立的运行时内核，与 application 解耦。

**StoryForge2** 采用「能力链 + OS 命名」模块化：

```
backend/
├── conductor/          状态机 + 断路器 + 检查点
├── creative_os/        创意发散引擎（Idea / Trope / Mutation / WhatIf）
├── story_os/           7 个叙事资产注册表
├── memory_os/          L0–L4 五层记忆
├── reader_os/          7 个读者状态指标
├── scene_engine/       Scene Schema 2.0 + 节拍模式
├── style_engine/       三层样式约束
├── agents/             6 个 LLM agent（planner / writer / reviewer / ...）
├── prompts/            YAML 提示词（直接存放，无分层）
└── api/                按 stage1–6 线性串接
```

### 1.3 关键差异

1. **关注点分离**：PlotPilot 的 domain 层零外部依赖，纯业务模型；StoryForge2 没有显式 domain 层，模型直接混入 `models/` 与 `memory_os/`。
2. **存储范式**：PlotPilot 用 SQLite + ORM 风格的 repositories + Write Dispatch 单写者派发；StoryForge2 用 JSON 文件 per project（`projects/{id}/storyos/*.json`），无事务。
3. **API 切分**：PlotPilot 按子域（world / blueprint / audit / reader / ...）；StoryForge2 按流水线阶段（stage1_concept → stage6_export），是流程式而非领域式。
4. **前端框架**：PlotPilot 用 Vue 3 + Naive UI + Vue Flow + ECharts + Tauri 桌面；StoryForge2 用 React 18 + Tailwind + xyflow + Recharts（无桌面端）。
5. **CLAUDE.md 同步度**：PlotPilot CLAUDE.md 与实际结构高度一致；StoryForge2 CLAUDE.md 严重过时，仍宣称「pre-implementation, no code yet」，但 `backend/` 实际已有 99 个文件上线。

---

## 二、核心逻辑对比

### 2.1 两条完全不同的设计哲学

> **PlotPilot 哲学**：「DDD 业务模型 + 引擎内核」—— 试图用工程化的领域抽象管理百万字叙事一致性。
>
> **StoryForge2 哲学**：「**确定性代码主导骨架，LLM 仅填血肉**」—— 把所有「机器能做」的检查 / 状态 / 检索全部下沉到 tier_0，LLM 只负责生成文字本身。

### 2.2 核心抽象对比

| 抽象 | PlotPilot | StoryForge2 |
|---|---|---|
| **状态管理** | Story Bible 聚合根 + 多个子聚合（cast / character / worldbuilding / structure / knowledge / evolution / memory） | 7 个独立的 Narrative Registry（Conflict / Promise / Mystery / Twist / Reveal / Goal / Expectation）+ 跨注册表外键级联 |
| **状态变更机制** | LLM 生成后由 Evolution Engine 做门控验证（gate validation） | Writer 在文中嵌入 `<!-- SF_LOG ... -->` 注释标签，**StoryOS Agent 用正则解析**，零 LLM 更新状态 |
| **记忆体系** | 双索引（章节内容向量 + 知识三元组 `(subject, relation, object)` 结构化语义混合） | 5 层显式分层：L0（运行时 500t）/ L1（最近 5 章）/ L2（摘要+时间线+关系图 ~8K）/ L3（Qdrant+BM25 混合 RRF）/ L4（与 StoryOS 同步 ~3K），检索优先级 L0→L1→L4→L2→L3 |
| **一致性保障** | Quality Monitor：每章张力分（0–10）、风格相似度漂移、俗套扫描；漂移触发**定向改写**而非回滚 | 6 条 Fact Guard 硬规则（全确定性，零 LLM）：时间线 / 状态 / 世界规则 / 注册表合规 / 必需日志 / 日志格式正则校验 + Narrative Guard（提示）+ Style Guard（仅日志） |
| **创意发散** | 没有显式创意引擎 | CreativeOS（Idea Pool / Trope Pool / Mutation 引擎[4 操作] / Contradiction 引擎[5 模板] / WhatIf 引擎[递归树 depth=3 breadth=4] / Genre Fusion / Novelty 4 维度评估） |
| **读者体验建模** | 间接（tension score / drift detection） | ReaderOS：7 个公式化指标（Curiosity / Tension / Satisfaction / Frustration / Fatigue / Addiction / Discussion Potential），**全部零 LLM 计算** |
| **样式控制** | Anti-AI 检测端点 + 风格相似度漂移 | 3 层样式引擎：L1 体裁模板 YAML / L2 写作公式（句子/对话量化规则）/ L3 禁忌正则匹配 |
| **生成流程** | 10 步 BaseStoryPipeline（context → plan → compose → review → ...） + LangGraph DAG 编排 | 8 步线性：Outline → ScenePlan → SceneWrite → 3 层 Review → Refine → ChapterAssembly → StoryOS/MemoryOS 更新 → ReaderOS 更新 |
| **断路器** | Daemon 内置 circuit breaker + checkpoint 快照 | 场景级：3 次重试带自动生成 hints → 第 3 次强制 pass 并附兼容说明 |
| **世界观规则** | power ceilings / cost required via log tag（如能） | 同样由 SF_LOG 标签声明；power ceiling 在 Fact Guard 中硬校验 |
| **信念变更** | Evolution Engine gate | 8 种白名单触发事件类型 + 「需 ≥2 个独立触发 + 当前章节 ≥1 个」规则 |
| **风格选择** | Prompt pack 切换（短篇 / 长篇 / 游戏剧本等 20+ 注入点） | 单一 stage4 写作流 + style_sandbox 渲染器 |
| **Checkpoints** | Snapshot Manager（按章节/场景检查点 + HEAD 回滚） | `.storyforge_checkpoint.json` 场景粒度（覆写模式） |

### 2.3 设计哲学的根本分歧

**PlotPilot** 把 LLM 当作「domain participant」——LLM 调用内嵌在用例服务里，用 Pydantic 模型包装 IO，由 application 层编排。状态变更是 LLM 推理后由代码做合法性校验。

**StoryForge2** 把 LLM 当作「**受约束的文本填充器**」——通过 SF_LOG 标签 + 确定性解析器建立了「**LLM 不能撒谎**」的硬约束。11 类日志标签强制 LLM 在生成时声明状态变化，再由正则解析器（零 LLM）原子化更新 7 个注册表，跨注册表级联（Mystery→revealed → Reveal→revealed → Expectation→fulfilled）。这是非常聪明的「让 LLM 自证清白」设计。

### 2.4 模型分层策略对比

**StoryForge2 的 tier 模型清晰得多**：

| Tier | 用途 | 模型 |
|---|---|---|
| 0 | 确定性（Fact Guard / Style Guard / StoryOS Agent / ReaderOS / TensionCurve / Plot State Machine） | **无 LLM** |
| 1 | 创意核心（场景写作 / 突变 / 矛盾引擎） | Claude Opus 4 / DeepSeek V4 |
| 2 | 分析（Narrative Guard / 状态机 / WhatIf） | Claude Sonnet 4 |
| 3 | 辅助（L1 重提取 / NoveltyEvaluator / StyleExtractor） | Claude Haiku |

PlotPilot 没有显式的 tier 路由；虽提到「Anthropic / OpenAI / Ark / Gemini」多 provider，但没有 cost-aware 的 tier 调度。

---

## 三、技术栈与依赖对比

### 3.1 后端 Python 依赖

| 项 | PlotPilot | StoryForge2 |
|---|---|---|
| Web 框架 | FastAPI ≥0.109 + Jinja2 + python-multipart | FastAPI 0.110 |
| 数据验证 | Pydantic ≥2.0 | Pydantic 2.6 + pydantic-settings |
| AI SDK | openai ≥1.65 + anthropic ≥0.40 + **volcengine-python-sdk[ark]**（豆包） | anthropic 0.39 + openai 1.12 + 自研 deepseek / minimax provider |
| HTTP | httpx 0.27 | httpx 0.27 |
| 实用工具 | python-dotenv + PyYAML + **json-repair** | python-dotenv + PyYAML + **tiktoken**（精确 token 计数） |
| 文档导出 | python-docx + ebooklib + lxml + fpdf2 | **无导出依赖**（仅 stage6_export 路由） |
| 向量 / 检索 | ChromaDB（默认）+ Qdrant（备选） + BGE/SBERT（local） + **Knowledge Triples 结构化混合** | **Qdrant 必选**（本地文件）+ **BAAI/bge-m3 嵌入** + **rank-bm25** + RRF 融合 |
| 测试 | pytest + pytest-asyncio | pytest + pytest-asyncio |

### 3.2 关键差异解读

1. **PlotPilot 用 json-repair**（LLM 输出 JSON 容错），StoryForge2 用 `tiktoken`（精确预算控制）—— 反映两个项目对 LLM 的不同假设：PlotPilot 信任 LLM 输出 + 修复；StoryForge2 把 LLM 当消耗品用 token 严格计费。
2. **StoryForge2 强依赖 bge-m3 + Qdrant + BM25**（混合检索是核心理念）；PlotPilot 提供多个本地 / 远程向量库可选。
3. **PlotPilot 有完整文档导出栈**（DOCX / EPUB / PDF），StoryForge2 没有——前者面向作者最终交付，后者聚焦生成过程。
4. **StoryForge2 没有 Ark（火山引擎）SDK**，主要面向 Claude / DeepSeek / 自研 MiniMax。

### 3.3 前端栈对比

| 项 | PlotPilot | StoryForge2 |
|---|---|---|
| 框架 | **Vue 3.5** | **React 18** |
| UI 库 | **Naive UI**（中文社区驱动） | **Tailwind CSS**（自定义样式） |
| 状态 | **Pinia** | （未明示，可能 Context + useState） |
| 图表 | **ECharts 6** | **Recharts** |
| DAG / 流程图 | **@vue-flow/core 1.48** | **@xyflow/react 12.11** |
| Markdown | marked + dompurify | react-markdown + remark-gfm |
| 桌面端 | **Tauri 2.x** | 无 |
| 代码检查 | vue-tsc + Vite | tsc + Vite |
| 测试 | — | Vitest + Testing Library + jest-axe |

### 3.4 测试基础设施

- PlotPilot：338 个测试文件，按 unit / integration / dag / e2e 分树，pytest marker（unit / integration / slow / asyncio）。
- StoryForge2：71 个测试文件，按子域分目录（`test_creative_os/` ...），用 Vitest 做前端测试。

---

## 四、潜在风险与优势对比

### 4.1 PlotPilot 风险

| 风险 | 等级 | 说明 |
|---|---|---|
| **架构复杂度爆炸** | 🔴 高 | 163K LOC + 4 层 DDD + 独立 engine 内核 + DAG 编排 + 多个 bounded context——学习曲线极陡，新人难以全局把握。CLAUDE.md 自己也承认要靠「五子系统心智模型」才能理解 |
| **过度的工程化** | 🟡 中 | 单个 chapter 生成走 StoryPipeline → EngineDaemon → WritingDelegate → StoryPipelineRunner → 10 步 BaseStoryPipeline；任何一层加 LLM 兜底逻辑都要跨层穿行 |
| **状态变更依赖 LLM 推理** | 🟡 中 | Evolution Engine 的 gate validation 是工程化校验，但状态变更的「识别」本身仍依赖 LLM 从章节文本抽取；prompt 漂移会污染所有下游 |
| **CLAUDE.md 修改未提交** | 🟢 低 | git status 显示 `M CLAUDE.md` 未提交，文档与代码可能出现短暂不一致 |
| **代码深度大但实质创新点分散** | 🟡 中 | 多个 engines（Evolution / Governance / Memory / Codex / Snapshot）并行存在，但彼此集成深度不明；可能存在「为架构而架构」 |

### 4.2 PlotPilot 优势

| 优势 | 说明 |
|---|---|
| ✅ **真正工程化的可维护性** | 任何 chapter 都可独立复现 / 回滚（Snapshot Manager + HEAD）；Write Dispatch 消除并发写冲突 |
| ✅ **20+ 提示词注入点 YAML 可覆盖** | 切换 prompt 风格不需改代码；`prompt_packages/bundle_meta.yaml` + `nodes/*/package.yaml` 形成版本化提示词资产 |
| ✅ **跨多 provider 兼容** | Anthropic / OpenAI / 火山引擎 Ark / Gemini 都接好了，国内可用性高 |
| ✅ **桌面端 + 导出完整** | Tauri 桌面打包 + DOCX / EPUB / PDF 三种导出——真正面向作者交付 |
| ✅ **Open Source 友好** | LICENSE 完整、CONTRIBUTORS 文件、CODEOWNERS、PR 模板都齐 |

### 4.3 StoryForge2 风险

| 风险 | 等级 | 说明 |
|---|---|---|
| **CLAUDE.md 严重过时** | 🔴 高 | 仍宣称「pre-implementation, no code yet」而 `backend/` 已有 99 文件；新人 onboarding 会被严重误导 |
| **文档严重不足** | 🔴 高 | `docs/` 只有 `design/` 与 `superpowers/`（后者是 Claude Code 插件目录），无 ARCHITECTURE / 无 README 充实说明 |
| **无 LICENSE / 无 CI** | 🟡 中 | 不利于开源分发；100+ 项目数据（`projects/proj_*`）全是 commit 历史——隐私风险 |
| **state machine 的 SF_LOG 强约束依赖 LLM 服从** | 🟡 中 | 11 类日志标签要求 LLM 严格按格式插入；任何模型降级或 prompt 微小变化都会让正则 parser 失败，触发断路器强制 pass——实际可能掩盖问题 |
| **混合检索强依赖 bge-m3** | 🟡 中 | 首次启动需下载 BAAI/bge-m3 模型（~2GB+），无网络 / 无 GPU 环境体验差 |
| **API 按 stage 切分** | 🟡 中 | 13 个 router 全部按流水线阶段命名（stage1_concept ... stage6_export），缺少域抽象，未来加新功能时要决定塞哪个 stage |
| **缺乏真正的一致性推理** | 🟡 中 | Fact Guard 是硬规则正则——能挡住逻辑硬伤，但抓不住「角色动机漂移」「隐含逻辑冲突」等深层问题 |

### 4.4 StoryForge2 优势

| 优势 | 说明 |
|---|---|
| ✅ **「确定性主导」的工程美学** | tier_0 把所有机器能做的工作全做了（StoryOS Agent 用正则解析 SF_LOG → 7 个注册表 + 跨表级联），LLM 调用次数与成本可控可预期 |
| ✅ **Novelty 评估体系完整** | 4 维度评估（市场饱和度 30% + 套路相似度 25% + 矛盾深度 25% + 讨论潜力 20%），市场导向 |
| ✅ **CreativeOS 创意发散引擎** | Mutation（反转 / 融合 / 升级 / 颠覆 4 操作）+ WhatIf（递归树 depth=3 breadth=4 → 84 节点）+ Genre Fusion（BFS 距离融合）+ Contradiction（5 模板加权 + 复合 1.3×），网文创作方法论清晰 |
| ✅ **ReaderOS 7 指标公式化** | 读者疲劳 / 上瘾 / 讨论潜力等全用公式计算（零 LLM），可解释可调试 |
| ✅ **Token 预算严格** | 每章 ~117.5K / 每卷 ~2.35M，per-chapter 与 per-scene 两层 context caching 节省 60% 组装开销 |
| ✅ **Checkpoint 场景粒度** | `.storyforge_checkpoint.json` 覆写模式，恢复时从 `pipeline_stage` 重放——失败恢复粒度细 |

---

## 五、综合判断与适用场景

### 5.1 两者本质是两条路线

**PlotPilot** 是「**工程派**」：试图用 DDD / 多层架构 / 多种引擎协作来硬扛长篇叙事的复杂度。代价是认知负担重、文件多、层级深；收益是可维护性、扩展性、跨 provider 兼容性好。

**StoryForge2** 是「**方法论派**」：用「确定性代码主导 + LLM 受约束填充」的原则，把生成流水线拆成 tier_0 / tier_1 / tier_2 / tier_3 明确分工。代价是创新点高度依赖 SF_LOG 强约束（模型降级会脆断）、文档严重缺失；收益是 token 成本可控、创意发散方法论扎实、Novelty 评估可解释。

### 5.2 各自的最佳适用场景

| 场景 | 推荐 |
|---|---|
| 中文网文批量生产（重市场、重爽点、重节奏） | **StoryForge2**（CreativeOS + ReaderOS 高度对位网文方法论） |
| 多 provider 兼容 + 国内可用性 + 桌面交付 | **PlotPilot**（Ark SDK + Tauri + 三种导出） |
| 需要演化复杂状态（人物弧光 / 物件追踪 / 事件流） | **PlotPilot**（Evolution Engine 完整建模） |
| 需要明确 ROI 与 token 预算 | **StoryForge2**（tier 分工 + 严格 token 计费） |
| 团队大、需要清晰的 bounded context 划分 | **PlotPilot**（DDD + Engines-as-bounded-contexts） |
| 快速 POC / 方法论验证 | **StoryForge2**（代码量小、CLAUDE.md 一份设计稿即可启动） |

### 5.3 相互可借鉴的点

- **PlotPilot 可吸收**：StoryForge2 的 tier_0 / tier_1 分工原则（特别是 Reviewer 三层 Guard 中的「硬规则 tier_0 + 软建议 tier_1」模式可降低对 LLM 兜底的依赖）；SF_LOG 标签机制可作为 StoryOS 状态变更的补充校验层。
- **StoryForge2 可吸收**：PlotPilot 的 DDD 域抽象（特别是 cast / character / worldbuilding / structure 等子聚合）+ Write Dispatch 单写者模式（避免 JSON 文件并发写）+ Snapshot Manager 检查点体系；并应**优先更新 CLAUDE.md、添加 LICENSE、补 README 与 CI**。
