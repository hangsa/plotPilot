# StoryForge2 提示词借鉴详细分析

> **配套文档**:
> - 上层对比:`docs/STORYFORGE2_COMPARISON.md`(项目级对比)
> - 底层基础设施:`docs/superpowers/specs/2026-07-02-storyos-integration-design.md`(tier_0 SF_LOG 数据层 Phase 1)
> - **本文档定位**:聚焦**提示词与策略层**的可借鉴分析,与上述两份互补
>
> - **日期**:2026-07-07
> - **状态**:Draft → 待 review
> - **目的**:为后续融合规划设计文档提供依据

---

## 0. 上下文回顾

plotPilot 的 CPMS(Centralized Prompt Management System)v5.3.6 已有 **76 个提示词节点**,组织为:

```
infrastructure/ai/prompt_packages/
├── bundle_meta.yaml             # 版本元数据
├── nodes/<node_key>/
│   ├── package.yaml             # id/category/variables/output_format
│   ├── system.md                # 系统提示词(平均 15-30 行)
│   └── user.md                  # 用户提示词模板
```

storyForge2 在 `backend/prompts/` 下有约 **25 个 YAML 提示词 + 15 个内联字符串**,采用 **4-Tier 模型分档** + **SF_LOG 注释标签** + **7 阶段状态机**。

两者的根本差异:

| 维度 | plotPilot | storyForge2 |
|---|---|---|
| 节点颗粒度 | 76 个细粒度(平均职责单一) | 25 个粗粒度(每个职责多) |
| 提示词长度 | 极短(平均 15-30 行) | 偏长(场景写作 ~60 行) |
| 验证机制 | 6 个 anti-ai-* LLM-as-judge | 6 条 Tier 0 正则 + 2 层 LLM 兜底 |
| 约束表达 | 散落各节点 | 集中于单文件多层硬约束段 |
| 创意发散 | 无 | CreativeOS 7 节点 |
| 模型分档 | 无显式分档 | 4-Tier(T0=无 LLM,T1=创意,T2=分析,T3=廉价) |

---

## 一、借鉴项 1:Tier 0 SF_LOG 验证层(杠杆最大)

### 1.1 storyForge2 的具体做法

**SF_LOG 标记机制**:正文末尾必须输出 JSON `{text: "..."}`,`text` 字段夹带 HTML 注释:

```
<!-- SF_LOG <type> key="val" -->
```

当前使用 11 类,但可减到 6-8 类:

| 类型 | 用途 |
|---|---|
| `character_state_change` | 角色身体/位置/情绪/认知变化 |
| `location_transition` | 物理位置切换 |
| `relationship_change` | 角色间关系变化 |
| `power_usage` | 力量使用 |
| `cost_declaration` | 力量使用代价声明 |
| `knowledge_acquired` | 角色获得新信息 |
| `foreshadow_plant` | 新伏笔埋下 |
| `foreshadow_paid` | 已有伏笔回收 |
| `twist_reveal` | 反转揭露 |
| `registry_create` | 创建叙事资产 |
| `character_relation_change` | 角色关系变更 |

**配套验证链**(全部跑在 `reviewer.py:71-374`):

| 验证层 | Tier | 文件:行 | 做什么 |
|---|---|---|---|
| `check_1_timeline` | T0 正则 | `reviewer.py` 内 | 位置切换连续性 |
| `check_2_character_state` | T0 字符串 | 同上 | taboos + unknown_to_character 字符串匹配 |
| `check_3_world_rules` | T0 正则 | 同上 | power_usage vs ceilings + cost_declaration |
| `check_4_asset_compliance` | T0 正则 | 同上 | SF_LOG 资产引用 vs StoryOS registry |
| `check_5_log_completeness` | T0 正则 | 同上 | 必需 SF_LOG 是否全部出现 |
| Semantic Precheck | T3 Haiku | `prechecker.py:90-104` | 漏掉的 SF_LOG(LLM 兜底) |
| Narrative Guard | T2 Sonnet | `reviewer.py:498-518` | 漂移检测(情绪/关系/行为/知识) |

每条 Fact Guard 失败触发 `scene_rewrite.yaml`,把具体错误当 retry_hints 注入下一轮。**整个验证链没有一次"完整 LLM-as-judge"**。

### 1.2 plotPilot 现状缺口

plotPilot 当前的审阅结构完全 LLM-as-judge:

- `anti-ai-chapter-audit`(26 行,LLM 判断 AI 味)
- `anti-ai-character-state-lock`(LLM 判断角色漂移)
- `anti-ai-behavior-protocol`(LLM 判断行为是否 OOC)
- `tension-scoring`(LLM 打 0-100 分)
- `review-timeline-consistency`(LLM 挑物理硬伤)
- `review-character-consistency` / `review-storyline-consistency` / `review-foreshadowing-usage`(全是 LLM)

**代价**:

1. **成本高**:每章审阅至少 8-10 次 LLM 调用,单章审阅成本可能高于写作本身
2. **不确定**:同章节两次跑 `tension-scoring` 可能 ±15 分浮动
3. **难以硬把关**:LLM-as-judge 在 5000 字后基本只能"印象打分"
4. **无可重放事实层**:出 bug 后无法用 grep 复现"为什么没过"

### 1.3 具体集成路径

**Step 1:定义 SF_LOG 类型枚举**

建议新建 `domain/sf_log/types.py`:

```python
# MVP 6-8 类(plotPilot 不需要 storyForge2 11 类那么细)
SF_LOG_TYPES = [
    ("character_state_change", "角色身体/位置/情绪/认知等可被后续章节引用的事实变化"),
    ("location_transition",     "物理位置切换"),
    ("relationship_change",     "角色间关系发生变化(信任/敌对/亲密)"),
    ("power_usage",             "力量/技能/资源被使用"),
    ("cost_paid",               "使用力量付出的代价"),
    ("knowledge_acquired",      "角色获得新信息(打破 unknown_to_character)"),
    ("foreshadow_plant",        "新伏笔埋下"),
    ("foreshadow_paid",         "已有伏笔回收"),
]
```

每个类型定义 metadata:{required_keys, validators}。validators 是纯 Python 函数,供 Tier 0 调用。

**Step 2:新增 CPMS 节点 `sf-log-emit`**

`package.yaml`:

```yaml
id: sf-log-emit
name: SF_LOG 强制输出指令
category: generation
description: 在 prose-generation 阶段要求 LLM 在正文中嵌入结构化 SF_LOG 标签
builtin: true
tags: [sf_log, generation, prose]
variables:
  - name: required_sf_logs
    type: list
    required: true
  - name: prose_body
    type: string
    required: true
output_format: text
```

`system.md`(短):

```
你是网文章节扩写模型。除生成正文外,你还必须在正文适当位置嵌入结构化事件标签,
供后续一致性校验使用。标签不影响读者阅读。
```

`user.md`(在 chapter-prose-generation 的 user.md 末尾追加):

```
【SF_LOG 强制要求】
你必须在正文适当位置插入以下结构化事件标签(HTML 注释格式,不影响读者阅读):
<!-- SF_LOG <type> key1="val1" key2="val2" -->

本章触发的预期事件类型(由前置 planning 节点提供):
{required_sf_logs}

每条 SF_LOG 必须满足:
- <type> 必须是允许的类型之一
- 必须填齐 required_keys
- 位置必须嵌在所描述事件的前后 200 字内
- 不要解释、不要注释、不要声明你在写 SF_LOG
```

**Step 3:新增 Tier 0 验证模块 `application/sf_log/fact_guard.py`**

完全不需要 LLM:

```python
class SFFactGuard:
    def check(self, prose: str, required_logs: list, character_taboos: list,
              character_unknowns: list, power_ceilings: dict) -> GuardResult:
        return GuardResult(
            timeline = self._check_timeline(prose),
            char_state = self._check_taboo_strings(prose, character_taboos),
            char_knowledge = self._check_unknowns(prose, character_unknowns),
            world_rules = self._check_power_usage(prose, power_ceilings),
            log_completeness = self._check_required_logs(prose, required_logs),
            asset_refs = self._check_asset_refs(prose),
        )
```

每个 check 返回 `(passed: bool, hits: list[Hit])`。Hit 是 `(location_offset, snippet, rule_id)`。

**Step 4:新增 CPMS 节点 `sf-log-semantic-precheck`(T3 兜底)**

参考 storyForge2 `semantic_precheck.yaml`(只有 3 类重点盯):只检测"剧情事件上确实发生但被 LLM 漏掉没打 SF_LOG 标签"的少数 case。这是 Tier 3 廉价调用。

**Step 5:新增 CPMS 节点 `sf-log-narrative-guard`(T2 漂移检测)**

参考 storyForge2 `narrative_guard.yaml`(情绪突变/关系突变/行为矛盾/知识泄漏 4 类),但要限制只检测 **SF_LOG 已记录事件之间** 的逻辑矛盾,不做整体风格评价。

**Step 6:DAG 路由**

```
chapter-prose-generation
  ↓
sf-log-fact-guard (Tier 0,必跑,失败触发 sf-log-rewrite-with-hints)
  ↓
sf-log-semantic-precheck (Tier 3,只对通过 fact-guard 的章节跑)
  ↓
sf-log-narrative-guard (Tier 2,同上)
  ↓
anti-ai-* 系列 (现有的 6 个,降级为"风格层"而非"事实层")
  ↓
tension-scoring
```

把 `review-gateway` / `retry-gateway` 节点改造为多结果路由,优先按 fact_guard 失败重写。

### 1.4 风险与代价

**收益**:
- 单章审阅成本预计降低 60-70%(把 8-10 次 LLM 调用压缩到 2-3 次,中间夹 1 次 Tier 0 纯 Python)
- 事实一致性问题(角色做了 taboo 列表的事)从"靠 LLM 印象"变成"字符串匹配 100% 准确"
- 调试可重放:SF_LOG 与 Hit 都是结构化数据,出 bug 可以精确回放

**风险**:
- prompt 增加 100-200 字,可能影响上下文窗口(需要验证 chapter_outline 大小)
- Tier 0 写错的正则会把 false positive 大量喂给 sf-log-rewrite,反而增加 LLM 调用 —— 需要 1-2 周调阈值
- SF_LOG 类型设计要谨慎,11 类太多、3 类太少;建议先做 6 类 MVP
- storyForge2 的 narrative_guard 在实战中也存在 "LLM 觉得没事就过" 的宽松问题,不能完全替代人工 review

**实现工作量**:中等

- 后端 4-5 个新文件 + 1-2 个 CPMS 节点 + DAG 接入
- 前端需要新增"SF_LOG 标签查看"页(可选,但能大幅提升调试体验)
- 单元测试覆盖每个 fact_guard check 的 5-10 个 case
- 真实章节回归测试(用 plotPilot 现有的测试样本 + storyForge2 公开样本各跑 20 章)

---

## 二、借鉴项 2:CreativeOS 创意子系统(从零开始的能力)

### 2.1 storyForge2 的具体做法

7 个独立提示词,覆盖创作前期的全部思考:

| 节点 | 输出 | 关键设计 |
|---|---|---|
| `whatif_expand.yaml` | 3 条互斥 whatif 路径 | 强制"互斥 / 逆向破局 / 跨类型嫁接 / 宏大尺度 / 主题深度 / 标志性画面" 6 条规则 |
| `mutation_operation.yaml` | 套路变异 4 种操作 | 反转/融合/升级/颠覆 |
| `trope_extraction.yaml` | 2-6 字套路标签 | 网文常见套路分类 |
| `genre_fusion.yaml` | 5 维度类型融合 | narrative_rhythm / character_archetype / conflict_type / world_rules / emotion_curve |
| `contradiction_expand.yaml` | 5 种矛盾模板展开 | ABILITY_VS_LIMIT / ETERNAL_VS_FLEETING / IDENTITY_VS_SECRET / GOAL_VS_COST / POWER_AS_WEAKNESS |
| `novelty_evaluation_llm.yaml` | 红海/蓝海评估 | 红海标志 + 蓝海提示 + 综合评估 |
| `branch_simulation_llm.yaml` | 分支模拟 | tension_curve / foreshadowing_risk / alternative_suggestions |

外加 `creative_director.py` 3 个内联角色(narrative guide / trope mutation analyst / planning consultant),形成"画布式发散探索"。

### 2.2 plotPilot 现状缺口

plotPilot **完全没有 CreativeOS 子层**。所有节点假设"用户带着清晰想法进来":

- `bible-*`(5 个):用户已知道题材、世界观、人物风格
- `macro-planning` / `planning-quick-macro` / `planning-precise-macro`:用户已决定全书结构
- `planning-main-plot-option` / `planning-plot-outline`:用户已在做主线选择

后果:

1. plotPilot **不能帮用户从零开始** —— 想试新方向必须先做完整 bible,门槛极高
2. plotPilot **没有横向借鉴能力** —— 同一个世界观无法快速试不同题材嫁接
3. plotPilot **没有反套路工具** —— 写作时发现落入俗套,没有"逆向破局"的提示词介入

### 2.3 具体集成路径

**MVP:先做 3 个节点,跑通完整链路**

**新节点 1:`creative-contradiction-expand`**

`system.md`(扩展到 8 个矛盾模板):

```
你是资深故事架构师,擅长从单一矛盾核心展开出可长期演化的长篇冲突。

【8 个矛盾模板(选 1-2 个展开)】
1. ABILITY_VS_LIMIT      能力越强边界越窄
2. ETERNAL_VS_FLEETING   永恒 vs 须臾(寿命/记忆)
3. IDENTITY_VS_SECRET    身份 vs 秘密
4. GOAL_VS_COST          目标 vs 代价
5. POWER_AS_WEAKNESS     力量即弱点
6. KNOWLEDGE_AS_BURDEN   知道越多越痛苦
7. BOND_AS_CHAIN         羁绊即枷锁
8. TRUTH_AS_DESTRUCTION  真相即毁灭
```

每个模板输出 `{element_a, element_b, core_tension, character_implications[], plot_implications[], thematic_depth}`,**直接喂给 plotPilot 的 `bible-characters` + `bible-worldbuilding` 节点**。

**新节点 2:`creative-whatif-expand`**

`system.md`(参考 storyForge2 的 6 条铁律):

```
你是具有破局思维的创意架构师,擅长从单一设定点发散出多条互斥的长篇演化路径。

【铁律】
1. 三条路径必须互斥:在 类型基调 / 核心冲突 / 主角命运 / 时间跨度 四个维度上必须明显区分。
2. 逆向破局:每条路径必须颠覆至少一个常见套路。
3. 跨类型嫁接:鼓励主类型与至少一个亚类型强制组合。
4. 宏大尺度:每条路径必须支持 100 万字以上的长篇结构。
5. 主题深度:必须涉及"自由意志 vs 命运""个体 vs 系统"等深层主题。
6. 标志性画面:每条路径必须有一个具体的"封面级"开场画面(50-80 字)。

【输出】
3 条 whatif 路径,每条 80-200 字,附 novelty_score (0-100) 和 trope_tags。
```

**新节点 3:`creative-genre-fusion`**

参考 `genre_fusion.yaml`,但简化为 plotPilot 已有的题材赛道枚举。

**完整链路**:

```
[用户输入种子设定]
  ↓
creative-contradiction-expand  → 选定核心矛盾
  ↓
creative-whatif-expand        → 3 条互斥路径,用户选 1
  ↓
creative-genre-fusion         → 选定题材嫁接组合
  ↓
bible-characters / bible-worldbuilding / bible-style-convention  ← 现有节点
  ↓
macro-planning                ← 现有节点
```

### 2.4 风险与代价

**收益**:

- plotPilot 从"执行机"升级为"构思 + 执行一体机",覆盖零基础用户
- CreativeOS 节点输出**与 plotPilot 现有 bible 节点契约完全兼容**(都是 JSON),集成成本极低
- 差异化卖点(国内没看到把 CreativeOS 工业化提示词化的先例)

**风险**:

- CreativeOS 输出质量极依赖 prompt 调优 —— storyForge2 也是经过多轮迭代才有现在效果
- 3 条 whatif 路径之间如果不够"互斥",用户体验会很差(感觉"差不多"),需要花时间打磨 novelty_score 标尺
- 可能引入认知负担 —— plotPilot 当前强调"网格填空"的简洁心智,CreativeOS 偏发散,两种哲学共存需要 UX 调和

**实现工作量**:小

- 后端 3-5 个新 CPMS 节点 + DAG 入口
- 前端需要"创意画布"UI 组件(参考 storyForge2 的 canvas 树,但 plotPilot 用 Vue Flow 已有 DAG 可视化基础)
- 提示词调优时间(无法预估,要看 LLM 响应质量)

---

## 三、借鉴项 3:character.taboos + unknown_to_character 硬约束

### 3.1 storyForge2 的具体做法

`character_generation.yaml` 在 voice_signature 段定义两个字段:

```yaml
voice_signature:
  speech_style: ...
  thought_patterns: ...
  taboos:
    - "绝对不会向外人透露家族丑闻"
    - "绝对不能在压力下抛弃队友"
  unknown_to_character:
    - "不知道自己其实是前朝遗孤"
    - "不知道师父与魔教有勾结"
```

**三个机制同时使用这两个字段**:

1. **`writer.py:28-76` 的 `_build_characters_context`** —— 直接拼到 writer 的 user prompt,标"绝对不能做"/"不能在文中出现"
2. **`reviewer.py` 的 `check_2_character_state`** —— Fact Guard 用字符串匹配:taboo 字符串出现在 prose 里直接 fail
3. **`narrative_guard.yaml` 的 knowledge_leak 检测** —— Tier 2 LLM 再做一次语义层面检测,避免被对话/转述绕过

### 3.2 plotPilot 现状缺口

plotPilot 把"角色不能做什么"分散在 3 个节点里,**没有强制 LLM 输出的硬约束源头**:

- `anti-ai-character-state-lock`(1 行 system:"角色当前身体、情绪、声线、信息边界和反应模式整理成不可违反的写作约束")
- `chapter-state-extraction`(从已生成章节反推状态变化)
- `bible-characters`(Casting Director 四层法,但没有显式 taboos/unknowns 字段)

**结果**:

1. 角色一致性靠 LLM 印象判断,**没有可枚举的硬约束清单**
2. 角色在长篇中"做了不在设定里的事",只能在 review 阶段靠 `review-character-consistency` 节点挑出来,然后整章返工
3. Fact Guard 缺失意味着每次返工都是 LLM-as-judge,成本高且不确定

### 3.3 具体集成路径

**Step 1:扩展 `bible-characters` 的 schema**

在 `domain/character/` 给 Character 实体新增 2 个字段:

```python
class Character:
    ...
    taboos: list[str]              # 绝对不能做的事(最多 10 条)
    unknown_to_character: list[str]  # 角色不知道的信息(最多 10 条)
```

**Step 2:改造 `bible-characters` 节点**

在 user.md 里加上明确的"必须输出 taboos 和 unknown_to_character 字段"指令,system.md 给出 8 种 taboo 类型的示例:

```
【taboos 必填字段示例(8 种类型)】
1. 行为禁忌:角色绝对不会在压力下做出 X 行为
2. 道德底线:角色绝对不会为了利益牺牲 Y
3. 关系红线:角色绝对不会主动背叛 Z
4. 信息封锁:角色绝对不会主动透露 W
5. 身体禁忌:角色绝对不会(因身体原因)做 V
6. 心理防御:角色在面对 U 时会本能逃避,不会正面应对
7. 价值锚点:角色绝对坚守某条价值,即使看似不理性
8. 仪式/习惯:角色有不可打破的仪式感或习惯

【unknown_to_character 必填字段示例】
1. 身世秘密
2. 关系真相
3. 历史真相
4. 世界真相
5. 自身真相
6. 他人意图
7. 未来未知
8. 知识缺口
```

**Step 3:改造 chapter-prose-generation 节点的 user.md**

新增 `character_constraints_block` 变量(由 `context-blueprint` 或新节点 `context-character-rules` 注入):

```
【角色约束硬锁(不可违反)】
{character_constraints_block}

每个约束的具体含义:
- taboos 中的行为:本章及后续章节不得让该角色做出
- unknown_to_character 中的信息:本章及后续章节不得让该角色获知、说出、暗示或反应该信息
  (除非剧情有显式的揭示节点)
```

**Step 4:新增 CPMS 节点 `fact-guard-character-state`**

Tier 0 纯字符串匹配,参考 storyForge2 的 check_2:

```python
def check_character_state(prose: str, characters: list[Character]) -> GuardResult:
    hits = []
    for char in characters:
        for taboo in char.taboos:
            predicate = extract_predicate(taboo)  # 简单规则:取最后一个动词短语
            if predicate in prose and char.name in surrounding_chars(prose):
                hits.append(Hit(char=char.name, type="taboo", text=taboo, location=...))
        for unknown in char.unknown_to_character:
            ...
    return GuardResult(passed=len(hits)==0, hits=hits)
```

**Step 5:与现有 `anti-ai-character-state-lock` 节点共存**

`anti-ai-character-state-lock` 不删除,但降级为"风格层"——只在 Tier 0 通过后跑,且只关注"软一致性"(说话风格漂移、决策模式异常等 taboos 字符串无法覆盖的部分)。

### 3.4 风险与代价

**收益**:

- 角色一致性 bug 反馈链从"事后返工"变成"事前预防 + 事后秒级验证"
- Tier 0 字符串匹配 accuracy 高达 99%(中文 taboo 谓词通常不会被引号/反讽绕过)
- 给 chapter-prose-generation 节点增加"硬约束源头",与现有的"细纲锚定铁规"互补

**风险**:

- 需要在 bible-characters 节点里**强制要求 LLM 输出 taboos/unknowns** —— schema 层硬约束,需要 application 层做字段验证
- "绝对不能做"在中文语境下容易被反讽/回忆绕过,需要 Tier 2 narrative_guard 兜底
- taboo 列表膨胀需要限制上限(建议每角色 ≤10 条),否则 Tier 0 调用会过慢

**实现工作量**:小

- 后端 2 个字段 + 1 个新 CPMS 节点 + 1 个新 fact_guard check
- 前端角色编辑页需要新增 taboos/unknowns 编辑组件
- 单元测试每个角色的 3-5 个典型 case

---

## 四、借鉴项 4:cost_system in-text 约束(世界观内部一致性)

### 4.1 storyForge2 的具体做法

`world_generation.yaml` 输出 power_system 字段时,**强制要求两个子字段**:

```yaml
power_system:
  name: ...
  description: ...
  stages: [初阶, 中阶, 高阶, 圆满]
  cost_system:
    description: "每次使用力量都会折损自身寿元"
    trigger: "power_usage"  # 触发器
    declaration_format: "寿元-10"  # 必须在文中以这个格式声明
  ceilings:
    - stage: 初阶
      max_output: 单人毁一城
    - stage: 中阶
      max_output: 一人灭一国
```

**两件事同时发生**:

1. `scene_writing.yaml` 在硬约束段明文要求:"Power usage must show cost_system in text" —— 让 LLM 使用力量时**必须**写出代价
2. `reviewer.py` 的 `check_3_world_rules` 用正则 `COST_DECLARATION_PATTERN` 验证:每条 `POWER_USAGE_PATTERN` 后面必须有对应的 `COST_DECLARATION_PATTERN`

这是"在写作时就预防"+"事后正则兜底"的双层机制。

### 4.2 plotPilot 现状缺口

plotPilot 的 `bible-worldbuilding` 节点 system.md 没有读到(估计也是短 system),但从 `bible-worldbuilding` 的目录命名看,它大概率**只生成世界观描述,没有强制 power_system + cost_system + ceilings 的结构化字段**。

后果:

1. 长篇到中段,作者力量体系很容易崩 —— plotPilot 的 review 节点 `review-storyline-consistency` 可能挑出问题,但 LLM-as-judge 在力量体系这种"硬逻辑"上经常失准
2. 没有 ceilings 概念,意味着 LLM 写作时可能在后期突破前期设定的能力上限
3. 没有 cost_system 概念,意味着力量使用没有"代价"叙事张力

### 4.3 具体集成路径

**Step 1:扩展 `bible-worldbuilding` 节点的输出 schema**

在 user.md 里强制要求:

```
【必填字段】
power_system:
  name: ...
  stages: [...]
  cost_system:
    description: ...
    trigger: power_usage
    declaration_format: ...  # 在文中如何写
  ceilings:
    - stage: ...
      max_output: ...
【选填字段】
core_rules: [...]  # 世界观硬规则
factions: [...]    # 阵营列表
```

**Step 2:扩展 `context-blueprint` 节点**

把 power_system 的 ceilings + cost_system 注入到 chapter-prose-generation 的 user.md:

```
【世界规则硬锁(不可违反)】
{power_ceilings_table}

力量使用必须遵守:
- 单次 power_usage 不得超过当前 stage 的 ceilings
- 每次 power_usage 必须显式写明代价(declaration_format)
- 不得跨越当前 stage 使用上一阶能力(除非剧情有显式突破节点)
```

**Step 3:新增 Tier 0 check `fact-guard-world-rules`**

```python
def check_world_rules(prose: str, power_system: PowerSystem,
                      chapter_stage: int) -> GuardResult:
    hits = []
    ceiling = power_system.ceiling_for(chapter_stage)
    usages = extract_power_usages(prose)  # 正则匹配 power_usage 模式
    for usage in usages:
        if usage.output_exceeds(ceiling):
            hits.append(Hit(type="ceiling_violation", usage=usage, ceiling=ceiling))
        if not has_cost_declaration(prose, usage, power_system.cost_system.declaration_format):
            hits.append(Hit(type="missing_cost_declaration", usage=usage))
    return GuardResult(passed=len(hits)==0, hits=hits)
```

**Step 4:DAG 挂接**

```
chapter-prose-generation
  ↓
[sf-log-fact-guard, fact-guard-character-state, fact-guard-world-rules]  ← 并行跑
  ↓ (任一失败)
sf-log-rewrite-with-hints  ← 注入具体违反规则
  ↓
[sf-log-semantic-precheck, sf-log-narrative-guard]  ← Tier 3/Tier 2 兜底
```

### 4.4 风险与代价

**收益**:

- 力量体系一致性 bug 的发现成本从"全章返工"降到"单点重写"
- Tier 0 正则在"是否声明代价"这类判断上 accuracy 接近 100%
- 给出"代价"叙事的可执行工具 —— plotPilot 之前完全靠 LLM 自觉

**风险**:

- `declaration_format` 字段是写死的字符串模板,如果不同章节需要不同格式,需要 schema 支持格式变体
- 玄幻/科幻/历史等不同题材的 cost_system 字段语义不同,需要一个"题材适配层"
- `extract_power_usages` 的正则设计困难 —— 中文动词变化丰富,初期会有大量 false positive

**实现工作量**:中等

- 后端 1 个字段扩展 + 1 个新 fact_guard check + context-blueprint 注入
- 单元测试覆盖每个题材的 3-5 个 power_usage / cost_declaration case
- 真实长篇回归测试(尤其玄幻/仙侠题材最容易爆力量)

---

## 五、落地优先级矩阵

按"杠杆 / 风险 / 工作量"三维度:

| 借鉴项 | 杠杆 | 风险 | 工作量 | **建议优先级** |
|---|---|---|---|---|
| **Tier 0 SF_LOG + 硬约束验证层** | 极高(成本-70%,一致性+30%) | 中(正则调优) | 中 | **P0** —— 4 周可上线,撬动整个审阅链 |
| **character.taboos + unknown_to_character 硬约束** | 高(角色一致性 bug 90% 消失) | 低(增量字段) | 小 | **P0**(可与 P0 合并做) |
| **CreativeOS 子系统** | 中(覆盖新用户群) | 中(prompt 调优周期长) | 小 | **P1** —— 1-2 周 MVP,3 周调优 |
| **cost_system in-text 约束** | 中(玄幻/仙侠题材强需求) | 中(题材适配) | 中 | **P1**(P0 的 fact_guard 顺手做 cost_system check) |

## 六、最优落地顺序

1. **第 1-2 周**:扩展 `bible-characters` 加 taboos/unknowns + 扩展 `bible-worldbuilding` 加 power_system + 3 个 Tier 0 fact_guard(字符匹配 + 字符串匹配 + 正则)
2. **第 3-4 周**:新增 SF_LOG 类型定义 + 改造 chapter-prose-generation 输出 SF_LOG + 接入 DAG 路由
3. **第 5-6 周**:CreativeOS 3 节点 MVP(contradiction / whatif / genre_fusion),先内部用
4. **第 7+ 周**:基于真实使用数据调优 Tier 0 正则阈值与 prompt 细节

---

## 七、与已有 StoryOS Phase 1 基础设施设计的关系

`docs/superpowers/specs/2026-07-02-storyos-integration-design.md` 已经规划了 StoryOS Phase 1(tier_0 SF_LOG 数据层),覆盖:

- domain layer 类型(SFLogRecord, TwistType, Clue, 8 Registry 实体)
- persistence layer(11 张表 + WriteDispatch 扩展 transaction)
- 引擎层接入点(StoryOSDelegate Step 1/3/5/6 钩子)
- 前端 StoryOSHub + 6 子视图
- 旧 Foreshadowing 数据迁移

**本文档(提示词层)与上述设计的边界**:

| 层 | Phase 1 文档负责 | 本文负责 |
|---|---|---|
| **数据模型** | ✅ SFLogRecord schema、8 Registry 实体、Clue 等 | ❌ |
| **持久化** | ✅ SQLAlchemy schema + WriteDispatch transaction | ❌ |
| **引擎钩子** | ✅ StoryOSDelegate Step 1/3/5/6 | ❌ |
| **API + 前端** | ✅ StoryOSHub + 6 子视图 | ❌ |
| **数据迁移** | ✅ 旧 Foreshadowing 转换 | ❌ |
| **LLM 提示词** | (Phase 1 仅规划 `sflog_directive` 注入点) | ✅ **SF_LOG 完整 prompt 模板 + 6 类类型定义 + character.taboos + cost_system** |
| **Tier 路由** | ❌ | ✅ **4-Tier 模型分档的 PromptGateway 路由规则** |
| **创意发散提示词** | (Phase 2 才有) | ✅ **CreativeOS 3 节点 MVP 提示词** |

**协作建议**:Phase 1 基础设施层先落地(`domain/storyos/` + persistence + WriteDispatch),本文的提示词层作为**Phase 1F / Phase 2A** 在其基础上构建。两层之间通过 `prompt_packages` 的变量契约对接,基础设施层不感知提示词层、提示词层通过注入点消费基础设施。

---

## 八、参考文件清单

### storyForge2 关键文件

```
backend/prompts/scene_writing.yaml                  # 主创作提示词(含 SF_LOG 硬约束)
backend/prompts/scene_rewrite.yaml                  # Fact Guard 失败重写
backend/prompts/semantic_precheck.yaml              # T3 兜底
backend/prompts/narrative_guard.yaml                # T2 漂移检测
backend/prompts/character_generation.yaml           # 含 taboos/unknowns
backend/prompts/world_generation.yaml               # 含 cost_system/ceilings
backend/prompts/creative/whatif_expand.yaml         # CreativeOS 核心
backend/prompts/creative/contradiction_expand.yaml  # CreativeOS 矛盾模板
backend/prompts/creative/genre_fusion.yaml          # CreativeOS 类型融合
backend/prompts/sf_log_suggestion.yaml              # 编辑 SF_LOG 建议
backend/agents/writer.py:7-76                       # _build_characters_context 等
backend/agents/reviewer.py:71-374                   # Fact Guard 6 条检查
backend/agents/reviewer.py:498-518                  # Narrative Guard 加载
backend/agents/base_agent.py:78-86                  # load_prompt helper
backend/semantic_precheck/prechecker.py:90-104      # Semantic Precheck 加载
config/model_tiers.yaml                             # 4-Tier 模型分档
```

### plotPilot 关键文件

```
infrastructure/ai/prompt_packages/bundle_meta.yaml  # CPMS 版本元数据
infrastructure/ai/prompt_packages/README.md         # CPMS 使用说明
infrastructure/ai/prompt_packages/nodes/<76 个节点>/package.yaml + system.md + user.md
domain/character/                                   # Character 实体(待扩展 taboos)
domain/worldbuilding/                               # Worldbuilding 实体(待扩展 power_system)
application/sf_log/                                 # (待新建) Tier 0 fact_guard
```