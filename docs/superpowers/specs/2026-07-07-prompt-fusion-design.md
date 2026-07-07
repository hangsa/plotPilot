# PlotPilot × StoryForge2 提示词层融合设计 spec

> **配套文档**(必读):
> - 上层对比:`docs/STORYFORGE2_COMPARISON.md`
> - 借鉴详细分析:`docs/superpowers/specs/2026-07-07-prompt-borrow-analysis.md`(本文档基础)
> - 数据层设计:`docs/superpowers/specs/2026-07-02-storyos-integration-design.md`(SFLogRecord 类型 + 11 张表 + WriteDispatch 扩展)
> - 字段契约:`docs/superpowers/specs/2026-07-02-storyos-asset-field-spec.md`
>
> - **日期**:2026-07-07(revised 2026-07-07)
> - **状态**:Draft → 待用户 review
> - **目标版本**:PlotPilot v1.3(v1.2 = StoryOS Phase 1)
> - **本文档定位**:**Tier 0 硬约束层**融合设计,仅覆盖 SF_LOG + character.taboos + cost_system 三项,**CreativeOS 暂不在本文档范围**(留待后续单独 spec)

---

## 0. 决策记录(Decisions)

| # | 议题 | 决策 | 依据 |
|---|---|---|---|
| Q1 | 交付节奏 | **单一阶段**:Phase 2A = SF_LOG 提示词 + Tier 0 fact_guard + character.taboos + cost_system 注入。CreativeOS 推迟到独立后续 spec | 用户明确要求本次先不做 CreativeOS |
| Q2 | SF_LOG 类型范围 | **减法到 6 类**:`character_state_change` / `relationship_change` / `knowledge_acquired` / `power_usage` / `foreshadow_plant` / `foreshadow_paid` | plotPilot 不需要 storyForge2 11 类那么细;`location_transition` 与 `character_state_change` 合并;`cost_declaration` 由 fact_guard-world-rules 单独管(不走 SF_LOG);`twist_reveal` / `registry_create` / `character_relation_change` 由 StoryOS 接管 |
| Q3 | Tier 0 失败的 retry 策略 | **两级重试 + 强制 pass**:第 1 次失败 → `sf-log-rewrite-with-hints`(注入 hit 信息);第 2 次失败 → 同上;第 3 次仍失败 → 强制 pass + 写入 warnings | 复用 StoryOS Phase 1 的 `SFLogComplianceGate` 模式;不让单章硬约束卡住整本书进度 |
| Q4 | character.taboos 字段是否必填 | **必填但可空列表**;`bible-characters` 节点 LLM 输出 schema 校验;`unknown_to_character` 同 | 零代价强制 schema,空列表表示"暂无硬约束",后续可填充 |
| Q5 | cost_system 题材适配层 | **Phase 2A 不做**:统一 schema(`name` / `stages` / `cost_system` / `ceilings`),题材差异由 `bible-worldbuilding` prompt 自然处理 | 用户未提及题材适配;Phase 2A 先跑通统一 schema 即可 |
| Q6 | 现有 anti-ai-* 节点命运 | **降级而非删除**:6 个节点全部从"事实层"降为"风格层",只在 Tier 0 + Tier 3 通过后跑;节点名不变,语义转为"风格建议" | 保留作者对"AI 味"的关注,但避免高成本 false positive |
| Q7 | Tier 路由 PromptGateway | 新增 `application/ai/prompt_gateway.py`,按节点 metadata 决定 Tier;SF_LOG fact_guard 类节点固定 T0,创意类节点默认 T1,分析类默认 T2,辅助类默认 T3 | 中央路由避免散落 |
| Q8 | 与 StoryOS Phase 1 衔接 | **Phase 2A 等 Phase 1A-1E 全部完成后再启动**;消费 Phase 1 的 SFLogRecord / PredeclaredChange 等类型 | 数据层稳定后再做提示词层 |
| Q9 | 前端改造 | **Phase 2A 不做新工作台**,仅在已有 anti-ai-* 页面增加"硬约束违反列表"展示(由 Tier 0 fact_guard 输出驱动) | 降低 Phase 2A 范围,聚焦后端验证链 |

---

## 1. 背景与目标

### 1.1 背景

plotPilot v1.2 引入 StoryForge2 的 SF_LOG 数据层基础设施(`2026-07-02-storyos-integration-design.md`),让 LLM 通过显式声明结构化事件标签 + 零 LLM 正则解析 + 8 Registry 跨表级联,把 narrative arc 状态管理从"LLM 推断"变为"LLM 显式声明"。

**仍未解决的三层缺口**(本次聚焦解决):

1. **审阅成本高**:plotPilot 现有 6 个 anti-ai-* + 4 种 gateway + tension-scoring 全是 LLM-as-judge,每章 8-10 次 LLM 调用,单章审阅成本可能高于写作本身
2. **角色一致性靠 LLM 印象**:plotPilot 把"角色不能做什么"散落在 3 个节点里,没有可枚举的硬约束清单,无法用字符串匹配做硬把关
3. **世界观内部一致性弱**:plotPilot 的 `bible-worldbuilding` 没有强制 `power_system.cost_system` / `ceilings` 结构化字段,长篇中段力量体系容易崩

### 1.2 目标

1. **降低审阅成本 60-70%**:把 plotPilot 当前 8-10 次 LLM 审阅调用压缩到 2-3 次,中间夹 1 次 Tier 0 纯 Python fact_guard
2. **硬一致性问题秒级定位**:角色做 taboo 列表中的事、power 突破 ceilings、必需 SF_LOG 缺失等"硬伤"由纯 Python 检测,debug 可重放
3. **世界观硬规则结构化**:`bible-worldbuilding` 节点强制输出 power_system + cost_system + ceilings 字段,在 prompt 层显式约束"力量使用必须明价"

### 1.3 非目标(Out of Scope)

- ❌ CreativeOS 创意发散子系统(留待后续独立 spec)
- ❌ 完整 11 类 SF_LOG 还原(本次只做 6 类)
- ❌ 反 AI 味风格检测的算法升级(只降级 anti-ai-* 节点语义,不删除)
- ❌ cost_system 题材自动适配(统一 schema,题材差异交给 prompt 自然处理)
- ❌ 旧 anti-ai-* 节点的完全替换
- ❌ 新前端工作台(只在已有页面增加违反列表展示)

---

## 2. 架构总览

### 2.1 一句话定位

**新增 4-Tier 模型分档 + Tier 0 验证服务 + SF_LOG 强制输出节点 + character.taboos + cost_system schema 强制**,与现有 76 个 CPMS 节点 + StoryOS Phase 1 数据层 + 10 步 BaseStoryPipeline 有机协作。

### 2.2 五子系统心智模型更新(在 Phase 1 基础上)

| 子系统 | v1.2(Phase 1 后) | v1.3(本文) | 变化 |
|---|---|---|---|
| 1. Narrative State Machine | EvolutionState + Foreshadowing + StoryOS 8 Registry + Bridge | + character.taboos / unknown_to_character + power_system.cost_system / ceilings | 角色与世界观的硬约束字段 |
| 2. Vector Retrieval Layer | ChromaDB + Qdrant + 知识三元组 | 不变 | 不变 |
| 3. Engine Runtime | EngineDaemon → StoryPipelineRunner + StoryOSDelegate | + Tier 路由 PromptGateway + Tier 0 fact_guard services | 路由与验证层 |
| 4. Prompt Strategy Layer | 76 CPMS 节点 + sflog_directive | + sf-log-emit + sf-log-rewrite-with-hints + sf-log-semantic-precheck + sf-log-narrative-guard + fact-guard-* 3 节点 + context-character-rules | 节点数量扩展到 ~83 |
| 5. Quality Monitor | 张力/漂移/俗套 + SF_LOG 合规率 6 指标 | + Tier 0 fact_guard hit rate + character.taboo violation count + power ceiling violation count | 指标扩展 |

### 2.3 4-Tier 模型分档

| Tier | 用途 | 默认模型 | 节点示例 |
|---|---|---|---|
| **T0** | 确定性验证(零 LLM) | 无 | fact-guard-*、sf-log-fact-guard、evolution_gate |
| **T1** | 创意核心 | Claude Opus 4 / DeepSeek V4 | chapter-prose-generation、planning-precise-macro、bible-characters |
| **T2** | 分析 | Claude Sonnet 4 | sf-log-narrative-guard、anti-ai-character-state-lock(降级)、tension-scoring |
| **T3** | 辅助 | Claude Haiku | sf-log-semantic-precheck、emotion-ledger-extraction、prop-event-extraction、chapter-summarizer |

**中央路由**:`application/ai/prompt_gateway.py` 按节点 metadata 的 `tier` 字段路由。CPMS 节点 `package.yaml` 新增可选 `tier: t0|t1|t2|t3` 字段,缺省按 `category` 推断。

### 2.4 Pipeline 集成图(10 步中的 Phase 2A 钩子点)

```
Step 1  context-load        → Phase 2A: 加载 character.taboos/unknowns + power_system
Step 2  plan-beats          → Phase 2A: planning-chapter-preplan 输出 required_sf_logs
Step 3  pre-write gate      → Phase 2A: 把 taboos + ceilings + required_logs 注入 sf-log-emit
Step 4  compose             → Phase 2A: chapter-prose-generation 输出正文 + SF_LOG 标签
Step 5  post-write gate     → Phase 2A:
                              ├ Tier 0: [sf-log-fact-guard, fact-guard-character-state, fact-guard-world-rules] 并行
                              ├ 任一失败 → sf-log-rewrite-with-hints (≤2 次)
                              ├ 第 3 次仍失败 → 强制 pass + warnings
                              └ 通过后 → sf-log-semantic-precheck (T3) + sf-log-narrative-guard (T2)
Step 6  apply-state ◄──     → Phase 1 已实现,不变
Step 7  summary             → 不变
Step 8  vectors             → 不变
Step 9  chronicles          → 不变
Step 10 checkpoint          → 不变
```

### 2.5 架构边界(新增模块)

```
domain/
  character/                    + taboos / unknown_to_character 字段
  worldbuilding/                + power_system.cost_system / ceilings / declaration_format 字段
  sf_log/                       (新建) types.py + contracts.py

application/
  ai/
    prompt_gateway.py           (新建) Tier 路由中央服务
    tier_router.py              (新建) 模型分档决策
  sf_log/
    fact_guard.py               (新建) T0 纯 Python 验证(3 个 guard)
    rewrite_with_hints.py       (新建) T1 重写(失败 retry)
    semantic_precheck.py        (新建) T3 LLM 兜底
    narrative_guard.py          (新建) T2 漂移检测

infrastructure/ai/prompt_packages/
  nodes/
    sf-log-emit/                (新建) T1
    sf-log-rewrite-with-hints/  (新建) T1
    sf-log-semantic-precheck/   (新建) T3
    sf-log-narrative-guard/     (新建) T2
    fact-guard-character-state/ (新建) T0 标记
    fact-guard-world-rules/     (新建) T0 标记
    context-character-rules/    (新建) T1
    chapter-prose-generation/user.md  (改造) 追加 SF_LOG 段
    bible-characters/system.md  (改造) 追加 8 类 taboo + 8 类 unknown 示例 + 必填字段
    bible-worldbuilding/system.md (改造) 追加 power_system schema + 必填字段
    context-blueprint/user.md   (改造) 注入 power_ceilings_table + cost_system 约束段
    anti-ai-* 6 个节点 package.yaml (改造) 新增 tier=t2 + semantic_layer=style

engine/runtime/
  prompt_gateway_delegate.py    (新建) Step 5 post-write gate 钩子
```

---

## 3. Components 详设

### 3.1 domain 字段扩展

#### 3.1.1 domain/character/ —— Character 实体新增字段

```python
class Character:
    ...  # 现有字段
    taboos: list[str] = []              # 绝对不能做的事(最多 10 条)
    unknown_to_character: list[str] = []  # 角色不知道的信息(最多 10 条)
```

**字段语义**:

- `taboos`:每个条目是一句中文谓词,如"绝对不会向外人透露家族丑闻"——Tier 0 用谓词关键词做字符串匹配
- `unknown_to_character`:每个条目是一句中文事实,如"不知道自己其实是前朝遗孤"——Tier 0 用关键词做字符串匹配,T2 narrative_guard 做语义兜底

**校验规则**:

- 列表非 None(`null` 在 ORM 层拒绝)
- 长度 ≤ 10(超出截断 + warning)
- 每条 5-100 字符(过短/过长拒绝 + warning)

#### 3.1.2 domain/worldbuilding/ —— PowerSystem 实体新增

```python
class PowerSystem(BaseModel):
    name: str
    description: str
    stages: list[str]                                    # e.g. ["初阶", "中阶", "高阶", "圆满"]
    cost_system: CostSystem
    ceilings: list[PowerCeiling]

class CostSystem(BaseModel):
    description: str                                       # e.g. "每次使用力量都会折损自身寿元"
    trigger: str = "power_usage"                           # 触发器
    declaration_format: str                                # 在文中以这个格式声明, e.g. "寿元-10"

class PowerCeiling(BaseModel):
    stage: str                                             # 阶段名
    max_output: str                                        # 单次最大输出描述, e.g. "单人毁一城"
    max_stage_threshold: int = 1                           # 该 stage 序号(用于章节对照)
```

**必填校验**:`bible-worldbuilding` 节点 LLM 输出必须包含 `power_system.name` / `stages` / `cost_system` / `ceilings` 四个字段,否则标记 bible 为 incomplete。

#### 3.1.3 domain/sf_log/types.py(6 类)

```python
from enum import Enum

class SFLogType(str, Enum):
    CHARACTER_STATE_CHANGE = "character_state_change"
    RELATIONSHIP_CHANGE = "relationship_change"
    KNOWLEDGE_ACQUIRED = "knowledge_acquired"
    POWER_USAGE = "power_usage"
    FORESHADOW_PLANT = "foreshadow_plant"
    FORESHADOW_PAID = "foreshadow_paid"

# 每类 required_keys(供 Tier 0 格式校验)
REQUIRED_KEYS = {
    SFLogType.CHARACTER_STATE_CHANGE: ["character", "new_state"],
    SFLogType.RELATIONSHIP_CHANGE: ["character_a", "character_b", "delta"],
    SFLogType.KNOWLEDGE_ACQUIRED: ["character", "fact"],
    SFLogType.POWER_USAGE: ["character", "power_name"],
    SFLogType.FORESHADOW_PLANT: ["foreshadow_id", "description"],
    SFLogType.FORESHADOW_PAID: ["foreshadow_id"],
}
```

### 3.2 application Tier 0 fact_guard 服务

#### 3.2.1 application/sf_log/fact_guard.py

```python
@dataclass
class Hit:
    rule_id: str
    location: int       # 字符偏移
    snippet: str        # 触发片段
    severity: str       # "error" | "warning"
    details: dict = field(default_factory=dict)

@dataclass
class GuardResult:
    passed: bool
    hits: list[Hit]
    duration_ms: int

class SFFactGuard:
    """T0 纯 Python,零 LLM 调用"""
    def check_log_format(self, prose: str) -> GuardResult:
        """正则匹配 SF_LOG 标签格式 <!-- SF_LOG <type> key="val" -->"""
    def check_required_logs(self, prose: str, required: list[PredeclaredChange]) -> GuardResult:
        """每个 required 必须出现至少 1 次"""
    def check_asset_refs(self, prose: str, registries: dict) -> GuardResult:
        """SF_LOG 中的资产名必须在 StoryOS registry 存在"""
```

#### 3.2.2 application/sf_log/character_state_guard.py

```python
class CharacterStateGuard:
    """T0 字符串匹配"""
    def check_taboos(self, prose: str, characters: list[Character]) -> GuardResult:
        """每个 character.taboos 条目提取谓词关键词,在 prose 中搜索 + 上下文角色名匹配"""
    def check_unknowns(self, prose: str, characters: list[Character]) -> GuardResult:
        """每个 character.unknown_to_character 条目提取关键词,在 prose 中搜索 + 上下文角色名匹配"""
```

**谓词提取启发式**(避免硬编码中文 NLP):

- 取每条 taboo 末尾 4-8 字作为 predicate(如"绝对不会向外人透露家族丑闻" → "透露家族丑闻")
- predicate 在 prose 中出现 + 同一段落(200 字内)出现角色名 → 算 hit
- 跳过引号包裹内容(避免反讽/回忆绕过)—— 简单启发式:检测 `"..."` `「...」` `他说:` 等

#### 3.2.3 application/sf_log/world_rules_guard.py

```python
class WorldRulesGuard:
    """T0 正则"""
    def check_power_ceilings(self, prose: str, power_system: PowerSystem,
                              chapter_stage: int) -> GuardResult:
        """提取 power_usage SF_LOG,验证输出描述不超当前 stage ceilings"""
    def check_cost_declarations(self, prose: str, power_system: PowerSystem) -> GuardResult:
        """每个 POWER_USAGE 标签周围 100 字内必须有符合 declaration_format 的声明"""
```

**正则模式**(Chinese-tuned):

```python
POWER_USAGE_PATTERN = re.compile(
    r'<!--\s*SF_LOG\s+power_usage[^>]*-->'
)
COST_DECLARATION_PATTERN_TEMPLATES = {
    "寿元-{n}": re.compile(r'寿元\s*[-−]\s*\d+'),
    "灵力-{n}": re.compile(r'灵力\s*[-−]\s*\d+'),
    "气血-{n}": re.compile(r'气血\s*[-−]\s*\d+'),
}
# declaration_format 由 PowerSystem.cost_system 提供,运行时生成正则
```

每个 guard 调用成本 < 50ms(纯字符串/正则),可并行跑。

### 3.3 application PromptGateway 与 Tier 路由

#### 3.3.1 application/ai/prompt_gateway.py

```python
class TierMismatchError(Exception):
    """T0 节点不应走 PromptGateway"""

class PromptGateway:
    def render(self, node_key: str, variables: dict) -> RenderedPrompt:
        """根据 node_key 的 tier 字段决定:
        - T0 → raise TierMismatchError(由 Tier 0 services 自己处理)
        - T1/T2/T3 → 调用对应 LLM provider
        """
        tier = self._get_tier(node_key)
        if tier == "t0":
            raise TierMismatchError(f"{node_key} 是 T0,不应走 PromptGateway")
        provider = self.tier_router.route(tier)
        return provider.generate(node_key=node_key, variables=variables)
```

#### 3.3.2 application/ai/tier_router.py

```python
class TierRouter:
    """从 config/model_tiers.yaml 读取模型配置,支持 override"""
    def route(self, tier: str) -> LLMProvider:
        config = self._load_config()  # YAML 缓存
        return self._build_provider(config[tier])
```

`config/model_tiers.yaml` 格式(参考 storyForge2):

```yaml
t0:
  type: none
t1:
  type: anthropic
  model: claude-opus-4
  max_tokens: 8192
  temperature: 0.7
t2:
  type: anthropic
  model: claude-sonnet-4
  max_tokens: 4096
  temperature: 0.3
t3:
  type: anthropic
  model: claude-haiku-4
  max_tokens: 2048
  temperature: 0.3
```

### 3.4 CPMS 节点清单(Phase 2A 新增 7 个)

| 节点 | Tier | system.md 行数 | 核心职责 |
|---|---|---|---|
| `sf-log-emit` | T1 | ~15 | 在 chapter-prose-generation 输出追加 SF_LOG 标签指令 |
| `sf-log-rewrite-with-hints` | T1 | ~30 | Tier 0 失败后重写,把 hit 信息当 retry_hints 注入 |
| `sf-log-semantic-precheck` | T3 | ~25 | 兜底检测漏掉的 SF_LOG(参考 storyForge2 同名 yaml) |
| `sf-log-narrative-guard` | T2 | ~35 | 漂移检测(情绪/关系/行为/知识 4 类) |
| `fact-guard-character-state` | T0 | (无 LLM) | 调用 CharacterStateGuard(`package.yaml` 标记 tier=t0,作为 Python 服务调用入口) |
| `fact-guard-world-rules` | T0 | (无 LLM) | 调用 WorldRulesGuard(同上) |
| `context-character-rules` | T1 | ~20 | 压缩 character.taboos/unknowns 到 context-blueprint 的子节点 |

**关于 T0 节点的 CPMS 表示**:不写 `system.md`,只写 `package.yaml` 标记 `tier: t0` + `handler: application.sf_log.character_state_guard.CharacterStateGuard`。`PromptGateway` 看到 T0 直接路由到 handler,不调用 LLM。

### 3.5 CPMS 改造节点清单(5 个)

| 节点 | 改造点 |
|---|---|
| `chapter-prose-generation/user.md` | 末尾追加 SF_LOG 强制输出段 |
| `bible-characters/system.md` | 追加 8 类 taboo + 8 类 unknown 示例 + 必填字段说明 |
| `bible-worldbuilding/system.md` | 追加 power_system 必填字段说明 + 5 类题材示例 |
| `context-blueprint/user.md` | 注入 `power_ceilings_table` + `cost_system` 约束段 |
| 6 个 `anti-ai-*` 节点 `package.yaml` | 新增 `tier: t2` + `semantic_layer: style`(语义降级为"风格层") |

#### 3.5.1 chapter-prose-generation/user.md 追加段

在现有正文细纲 + 硬约束段之后,**末尾**追加:

```
【SF_LOG 强制要求】
你必须在正文适当位置插入以下结构化事件标签(HTML 注释格式,不影响读者阅读):
<!-- SF_LOG <type> key1="val1" key2="val2" -->

本章触发的预期事件类型(由前置 planning 节点提供):
{required_sf_logs}

【6 类允许的类型】
- character_state_change: 角色身体/位置/情绪/认知等可被后续章节引用的事实变化
  必须字段: character, new_state
- relationship_change: 角色间关系发生变化(信任/敌对/亲密)
  必须字段: character_a, character_b, delta
- knowledge_acquired: 角色获得新信息(打破 unknown_to_character)
  必须字段: character, fact
- power_usage: 力量/技能/资源被使用
  必须字段: character, power_name
- foreshadow_plant: 新伏笔埋下
  必须字段: foreshadow_id, description
- foreshadow_paid: 已有伏笔回收
  必须字段: foreshadow_id

【插入规则】
- 位置必须嵌在所描述事件的前后 200 字内
- 必须在 required_sf_logs 列出的事件全部出现(可一条 SF_LOG 覆盖多个事件)
- 不要解释、不要注释、不要声明你在写 SF_LOG
- HTML 注释格式与正文融为一体,读者看不到
```

#### 3.5.2 bible-characters/system.md 追加段

```
【必填字段】taboos + unknown_to_character

【8 类 taboos(选 3-8 条填入)】
1. 行为禁忌: 角色绝对不会在压力下做出 X 行为
2. 道德底线: 角色绝对不会为了利益牺牲 Y
3. 关系红线: 角色绝对不会主动背叛 Z
4. 信息封锁: 角色绝对不会主动透露 W
5. 身体禁忌: 角色绝对不会(因身体原因)做 V
6. 心理防御: 角色在面对 U 时会本能逃避
7. 价值锚点: 角色绝对坚守某条价值
8. 仪式/习惯: 角色有不可打破的仪式感

每条填写格式: "绝对不会 + 谓词 + 对象"
例: ["绝对不会向外人透露家族丑闻", "绝对不能在压力下抛弃队友"]

【8 类 unknown_to_character(选 3-8 条填入)】
1. 身世秘密: 角色不知道自己的真实出身
2. 关系真相: 角色不知道某人与自己的真实关系
3. 历史真相: 角色不知道某历史事件的真相
4. 世界真相: 角色不知道世界运行的某个关键机制
5. 自身真相: 角色不知道自己的某个心理/生理特征
6. 他人意图: 角色不知道他人对某行为的真实意图
7. 未来未知: 角色不知道某事件即将发生
8. 知识缺口: 角色不掌握某种关键技术或语言

每条填写格式: "不知道 + 事实"
例: ["不知道自己其实是前朝遗孤", "不知道师父与魔教有勾结"]

【硬约束】
- 两个字段必须存在(可为空列表 [])
- 每条 5-100 字符
- 列表长度 ≤ 10
```

#### 3.5.3 bible-worldbuilding/system.md 追加段

```
【必填字段】power_system(无论题材是否涉及力量体系)

{
  "name": "力量体系名称",
  "description": "一句话描述",
  "stages": ["初阶", "中阶", "高阶", "圆满"],
  "cost_system": {
    "description": "每次使用力量付出的代价",
    "trigger": "power_usage",
    "declaration_format": "代价格式,如'寿元-{n}'"
  },
  "ceilings": [
    {"stage": "初阶", "max_output": "单人毁一城", "max_stage_threshold": 1},
    {"stage": "中阶", "max_output": "一人灭一国", "max_stage_threshold": 2},
    {"stage": "高阶", "max_output": "改天换地", "max_stage_threshold": 3},
    {"stage": "圆满", "max_output": "毁天灭地", "max_stage_threshold": 4}
  ]
}

【题材适配】
- 玄幻/仙侠: cost = 寿元/灵力/气血
- 科幻: cost = 能量/精神负荷/装备损耗
- 历史/权谋: cost = 人情/政治资本/承诺
- 悬疑/推理: cost = 线索可信度/证人安全
- 都市/言情: cost = 信任/机会/金钱

无论题材,schema 统一。
```

#### 3.5.4 context-blueprint/user.md 追加段

```
【世界规则硬锁(不可违反)】

power_system:
  name: {power_system.name}
  stages: {power_system.stages}
  current_stage: {current_stage}  # 由 chapter_stage 决定

ceilings(当前 stage):
  max_output: {current_ceiling.max_output}

cost_system:
  description: {cost_system.description}
  declaration_format: {cost_system.declaration_format}  # 例: "寿元-{n}"

【力量使用硬规则】
- 单次 power_usage 不得超过当前 stage 的 max_output
- 每次 power_usage 必须显式按 declaration_format 写明代价
- 不得跨越当前 stage 使用上一阶能力(除非剧情有显式突破节点)
```

#### 3.5.5 anti-ai-* 节点降级

6 个节点 `package.yaml` 改造示例(以 `anti-ai-character-state-lock` 为例):

```yaml
id: anti-ai-character-state-lock
name: 角色状态漂移审查(风格层)
category: review
description: |
  从风格角度检查角色说话风格/决策模式是否漂移。
  注意:本节点已降级为风格层,事实一致性由 Tier 0 fact-guard-character-state 负责。
  本节点仅在 Tier 0 + Tier 3 通过后跑,且只关注软一致性。
tier: t2
semantic_layer: style
tags: [review, style, anti-ai]
```

### 3.6 DAG 路由与引擎钩子

#### 3.6.1 engine/runtime/prompt_gateway_delegate.py

```python
class PromptGatewayDelegate:
    """Phase 2A 在 Step 5 post-write gate 接入"""
    def __init__(self, repo, character_service, worldbuilding_service,
                 planning_service, warning_service, llm_provider):
        ...

    def execute_post_write_fact_guard(self, chapter_id: int) -> FactGuardReport:
        prose = self.repo.get_chapter_body(chapter_id)
        characters = self.character_service.get_active(chapter_id)
        power_system = self.worldbuilding_service.get_power_system(chapter_id)
        required_logs = self.planning_service.get_required_sf_logs(chapter_id)

        # T0 三个 fact_guard 并行
        with ThreadPoolExecutor(max_workers=3) as executor:
            sf_fut = executor.submit(SFFactGuard().check, prose, required_logs)
            char_fut = executor.submit(CharacterStateGuard().check, prose, characters)
            world_fut = executor.submit(WorldRulesGuard().check, prose, power_system)
            sf_result = sf_fut.result()
            char_result = char_fut.result()
            world_result = world_fut.result()

        all_hits = sf_result.hits + char_result.hits + world_result.hits
        return FactGuardReport(passed=len(all_hits) == 0, hits=all_hits)

    def execute_rewrite_if_needed(self, chapter_id: int, report: FactGuardReport,
                                   attempt: int) -> bool:
        """两级重试 + 强制 pass"""
        if report.passed or attempt >= 3:
            if attempt >= 3:
                self.warning_service.record(chapter_id, report.hits)
            return True
        # 调用 sf-log-rewrite-with-hints
        return self.rewrite_with_hints(chapter_id, report.hits)

    def execute_t2_t3_supplement(self, chapter_id: int) -> SupplementReport:
        """Tier 0 通过后跑 sf-log-semantic-precheck (T3) + sf-log-narrative-guard (T2)"""
        ...
```

#### 3.6.2 DAG 接入点

`engine/runtime/engine_daemon.py` 在 Step 5 处插入调用:

```python
def step5_post_write_gate(self, chapter_id: int):
    delegate = self.runtime.get(PromptGatewayDelegate)
    for attempt in range(3):
        report = delegate.execute_post_write_fact_guard(chapter_id)
        if delegate.execute_rewrite_if_needed(chapter_id, report, attempt):
            break
    if report.passed:
        delegate.execute_t2_t3_supplement(chapter_id)
```

---

## 4. 阶段目标与产出物

### 4.1 Phase 2A — SF_LOG + Tier 0 + character.taboos + cost_system(Week 1-4)

**前置条件**:StoryOS Phase 1A-1E 全部完成,`SFLogRecord` / `PredeclaredChange` 等类型已落地

#### Week 1-2:基础设施层

| 任务 | 文件 | 验收 |
|---|---|---|
| Character 实体扩展 taboos/unknowns 字段 + ORM 迁移 | `domain/character/`,`infrastructure/persistence/migrations/versions/0002_*.py` | 单元测试 schema 校验 |
| PowerSystem/CostSystem/PowerCeiling 实体 + ORM 迁移 | `domain/worldbuilding/`,`infrastructure/persistence/migrations/versions/0002_*.py` | 单元测试 schema 校验 |
| domain/sf_log/types.py 6 类定义 | `domain/sf_log/types.py` | enum 完整性测试 |
| SFFactGuard 实现 | `application/sf_log/fact_guard.py` | 5-10 个 unit case |
| CharacterStateGuard 实现(含谓词提取启发式) | `application/sf_log/character_state_guard.py` | 5-10 个 unit case |
| WorldRulesGuard 实现(含正则模板) | `application/sf_log/world_rules_guard.py` | 5-10 个 unit case |
| bible-characters LLM 输出 schema 校验 | `application/character/bible_validator.py` | LLM 响应 Pydantic 校验 |
| bible-worldbuilding LLM 输出 schema 校验 | `application/worldbuilding/bible_validator.py` | LLM 响应 Pydantic 校验 |

#### Week 3:CPMS 节点 + 现有节点改造

| 任务 | 文件 | 验收 |
|---|---|---|
| 新增 sf-log-emit CPMS 节点 | `infrastructure/ai/prompt_packages/nodes/sf-log-emit/` | 节点可加载,变量注入正确 |
| 新增 sf-log-rewrite-with-hints CPMS 节点 | `infrastructure/ai/prompt_packages/nodes/sf-log-rewrite-with-hints/` | 同上 |
| 新增 sf-log-semantic-precheck CPMS 节点 | `infrastructure/ai/prompt_packages/nodes/sf-log-semantic-precheck/` | 同上 |
| 新增 sf-log-narrative-guard CPMS 节点 | `infrastructure/ai/prompt_packages/nodes/sf-log-narrative-guard/` | 同上 |
| 新增 fact-guard-* 2 个 T0 CPMS 标记节点 | `infrastructure/ai/prompt_packages/nodes/fact-guard-*/package.yaml` | tier=t0 + handler 正确 |
| 新增 context-character-rules CPMS 节点 | `infrastructure/ai/prompt_packages/nodes/context-character-rules/` | 同上 |
| chapter-prose-generation/user.md 追加 SF_LOG 段 | `infrastructure/ai/prompt_packages/nodes/chapter-prose-generation/user.md` | 模板渲染测试 |
| bible-characters/system.md 追加 8+8 类示例 | `infrastructure/ai/prompt_packages/nodes/bible-characters/system.md` | 模板渲染测试 |
| bible-worldbuilding/system.md 追加 power_system 字段 | `infrastructure/ai/prompt_packages/nodes/bible-worldbuilding/system.md` | 同上 |
| context-blueprint/user.md 注入世界规则硬锁 | `infrastructure/ai/prompt_packages/nodes/context-blueprint/user.md` | 同上 |
| 6 个 anti-ai-* 节点降级(tier=t2 + semantic_layer=style) | `infrastructure/ai/prompt_packages/nodes/anti-ai-*/package.yaml` | 同上 |

#### Week 4:PromptGateway + 引擎集成 + 回归测试

| 任务 | 文件 | 验收 |
|---|---|---|
| PromptGateway + TierRouter 实现 | `application/ai/prompt_gateway.py`,`application/ai/tier_router.py` | 单元测试 |
| config/model_tiers.yaml 创建 | `config/model_tiers.yaml` | 4-Tier 配置加载测试 |
| PromptGatewayDelegate 实现 + Step 5 集成 | `engine/runtime/prompt_gateway_delegate.py`,`engine/runtime/engine_daemon.py` | DAG 集成测试 |
| 单元测试覆盖率 ≥ 80% | `tests/unit/sf_log/`,`tests/unit/ai/`,`tests/unit/character/`,`tests/unit/worldbuilding/` | pytest --cov |
| DAG 集成测试 | `tests/dag/test_post_write_fact_guard.py` | 端到端跑通 |
| 回归测试:20 章样本 | `tests/regression/test_phase2a_real_chapters.py` | 全部命中期望 |
| 性能基准:Tier 0 fact_guard 单章 < 100ms | `tests/performance/test_fact_guard_latency.py` | < 100ms P95 |

#### Week 4 末验收

- ✅ 跑通 20 章回归测试(用 plotPilot 现有测试样本 + storyForge2 公开样本各 10 章)
- ✅ T0 fact_guard 单章平均 < 100ms
- ✅ L1 调用次数从 8-10 降到 2-3
- ✅ character.taboos 违反漏检率 < 5%
- ✅ power 突破 ceilings 漏检率 < 5%

---

## 5. 风险登记

| 风险 | 等级 | 触发条件 | 缓解措施 |
|---|---|---|---|
| Tier 0 正则 false positive 高 | 🟡 中 | 中文动词变化丰富,power_usage / cost_declaration 难匹配 | Week 4 末留 3-5 天阈值调优窗口;允许 `config/fact_guard_overrides.yaml` 用户自定义 regex |
| SF_LOG 标签格式被 LLM 偶尔写错 | 🟡 中 | 模型降级或 prompt 微小变化 | T3 semantic_precheck 兜底;StoryOS Phase 1 的 FormatError 复用 |
| character.taboos 被反讽/回忆绕过 | 🟡 中 | LLM 在角色独白或转述中提及 taboo | T2 sf-log-narrative-guard 兜底;谓词启发式跳过引号内容 |
| anti-ai-* 降级导致漏判 | 🟢 低 | 风格层覆盖变薄 | 保留节点只降级语义,后续算法升级空间保留;Week 4 末做风格漏判率回归 |
| power_system cost 表达方式题材差异大 | 🟢 低 | 玄幻/历史/悬疑 cost 表达完全不同 | Phase 2A 接受简化,5 类题材示例在 bible-worldbuilding prompt 中提供 |
| Phase 2A 与 StoryOS Phase 1E 迁移冲突 | 🟢 低 | 旧 Foreshadowing 迁移期间同时改造 | 严格串行:Phase 1E 完成后才启动 Phase 2A |
| 谓词启发式误判(谓词过短/过长) | 🟡 中 | taboo 文本长度不规范 | 5-100 字符校验已加;Week 4 末做 50 个真实样本回测 |

---

## 6. 成功指标

### 6.1 Phase 2A 上线 4 周后

| 指标 | 当前基线 | 目标 |
|---|---|---|
| 单章 LLM 审阅调用次数 | 8-10 | 2-3 |
| 单章审阅平均耗时 | ~120s | ~40s |
| 单章审阅平均 token 消耗 | ~50K | ~15K |
| 角色 taboo 违反漏检率 | ~30%(LLM 印象) | < 5%(T0 字符串) |
| power 突破 ceilings 漏检率 | ~40% | < 5% |
| power 缺 cost_declaration 漏检率 | ~50%(几乎无检查) | < 5% |
| SF_LOG 格式合规率 | (无) | > 95% |
| Tier 0 fact_guard 单章耗时 | (无) | < 100ms P95 |
| Debug 时定位"为什么这章没过"时间 | ~10 分钟 | < 1 分钟(直接 grep hits) |
| bible-characters 含 taboos 字段的 schema 合规率 | (无字段) | > 90% |
| bible-worldbuilding 含 power_system 字段的 schema 合规率 | (无字段) | > 90% |

---

## 7. 与相关文档/系统的接口

### 7.1 上游依赖

- `docs/superpowers/specs/2026-07-02-storyos-integration-design.md` §3.1(类型清单)、§3.3(SF_LOG→Evolution 映射)
- `docs/superpowers/specs/2026-07-02-storyos-asset-field-spec.md`(SFLogRecord 6 字段,Clue 9 字段,TwistType 6 值)
- Phase 1A-1E 全部完成

### 7.2 下游消费

- Phase 2A 输出供 `engine/runtime/storyos_delegate.py`(Phase 1)消费 `PredeclaredChange` / `SFLogRecord`
- 4-Tier 模型分档供未来所有新节点参考
- 现有 `prop-event-extraction` / `emotion-ledger-extraction` 节点的输出可与 SF_LOG 标签互为补充(都从章节正文抽取结构化事件)

### 7.3 命名与 schema 约定

- 新 CPMS 节点 `id` 字段 snake_case,以功能命名(`sf-log-*` / `fact-guard-*` / `context-character-rules`)
- `tier` 字段:`t0` / `t1` / `t2` / `t3`
- `semantic_layer` 字段(可选):`fact` / `style` / `analysis` / `creative`,与 tier 正交
- Tier 0 节点在 CPMS 不放 `system.md`(只放 `package.yaml` 标记 tier=t0 + handler 路径),实际是 Python 服务调用入口

---

## 8. 参考文件清单

### 上游
- `docs/STORYFORGE2_COMPARISON.md`(项目级对比)
- `docs/superpowers/specs/2026-07-07-prompt-borrow-analysis.md`(本文档基础)
- `docs/superpowers/specs/2026-07-02-storyos-integration-design.md`
- `docs/superpowers/specs/2026-07-02-storyos-asset-field-spec.md`

### storyForge2 参考实现
- `backend/prompts/scene_writing.yaml` —— SF_LOG 注入范本
- `backend/prompts/scene_rewrite.yaml` —— retry_hints 范本
- `backend/prompts/semantic_precheck.yaml` —— T3 兜底范本
- `backend/prompts/narrative_guard.yaml` —— T2 漂移检测范本
- `backend/prompts/character_generation.yaml` —— taboos/unknowns 字段范本
- `backend/prompts/world_generation.yaml` —— power_system 范本
- `backend/agents/writer.py:7-76` —— `_build_characters_context` 范本
- `backend/agents/reviewer.py:71-374` —— Fact Guard 6 条范本
- `backend/agents/reviewer.py:498-518` —— Narrative Guard 加载范本
- `backend/semantic_precheck/prechecker.py:90-104` —— Semantic Precheck 加载范本
- `config/model_tiers.yaml` —— 4-Tier 模型分档范本

### plotPilot 现有相关
- `infrastructure/ai/prompt_packages/bundle_meta.yaml`
- `infrastructure/ai/prompt_packages/nodes/chapter-prose-generation/{system,user}.md`
- `infrastructure/ai/prompt_packages/nodes/bible-characters/system.md`
- `infrastructure/ai/prompt_packages/nodes/bible-worldbuilding/system.md`
- `infrastructure/ai/prompt_packages/nodes/context-blueprint/system.md`
- `infrastructure/ai/prompt_packages/nodes/anti-ai-*` 6 个节点
- `domain/character/` + `domain/worldbuilding/`
- `application/ai_invocation/`
- `engine/runtime/engine_daemon.py`
- `engine/runtime/storyos_delegate.py`(Phase 1 实现)
- `config/`(待新建 `model_tiers.yaml`)