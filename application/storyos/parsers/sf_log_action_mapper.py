"""SFLogActionMapper — 11 类 SF_LOG → 6 EvolutionAction + 5 跳过（spec §3.3 锁定）。

spec §3.3 锁定映射表（关键，不要改）：
  6 mapped: CHARACTER_LOCATION_CHANGE / CHARACTER_PHYSICAL_CHANGE / CHARACTER_RELATION_CHANGE /
             KNOWLEDGE_GAIN / CONFLICT_ESCALATE / GOAL_MILESTONE
  5 skipped: CHARACTER_EMOTION / MYSTERY_CLUE / TWIST_REVEAL / EXPECTATION_FULFILL / REGISTRY_CREATE

设计原则（spec §3.3 锁定）：仅覆盖触发 EvolutionState 中事实型数据变更的 SF_LOG。
纯叙事资产操作（clue/reveal/emotion/expectation）只写 StoryOS，不进 Evolution。
"""
from __future__ import annotations

import uuid

from domain.evolution.contracts import ActionType
from domain.evolution.models import EvolutionAction
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord


# spec §3.3 锁定 6 映射（key=SFLogType, value=ActionType）
_MAPPED_LOG_TYPES: dict[SFLogType, ActionType] = {
    SFLogType.CHARACTER_LOCATION_CHANGE: ActionType.MOVE_CHARACTER,
    SFLogType.CHARACTER_PHYSICAL_CHANGE: ActionType.SET_CHARACTER_STATUS,
    SFLogType.CHARACTER_RELATION_CHANGE: ActionType.SET_EMOTIONAL_RESIDUE,
    SFLogType.KNOWLEDGE_GAIN: ActionType.REVEAL_FACT,
    SFLogType.CONFLICT_ESCALATE: ActionType.UPDATE_STORYLINE_PROGRESS,
    SFLogType.GOAL_MILESTONE: ActionType.UPDATE_DEBT_PROGRESS,
}

# spec §3.3 锁定 5 NOT_MAPPED（防御性常量，供其他模块引用）
NOT_MAPPED_LOG_TYPES: frozenset[SFLogType] = frozenset({
    SFLogType.CHARACTER_EMOTION,
    SFLogType.MYSTERY_CLUE,
    SFLogType.TWIST_REVEAL,
    SFLogType.EXPECTATION_FULFILL,
    SFLogType.REGISTRY_CREATE,
})


class SFLogActionMapper:
    """SFLogRecord → (EvolutionAction 列表, 跳过的 log_type 集合)。"""

    def map_records(
        self, records: list[SFLogRecord],
    ) -> tuple[list[EvolutionAction], set[SFLogType]]:
        actions: list[EvolutionAction] = []
        skipped: set[SFLogType] = set()
        for rec in records:
            action_type = _MAPPED_LOG_TYPES.get(rec.log_type)
            if action_type is None:
                skipped.add(rec.log_type)
                continue
            actions.append(
                EvolutionAction(
                    action_id=str(uuid.uuid4()),
                    type=action_type.value,
                    payload=dict(rec.params),
                    confidence=1.0,
                    source_refs=[{
                        "chapter_id": rec.chapter_id,
                        "char_position": rec.char_position,
                        "raw": rec.raw,
                    }],
                )
            )
        return actions, skipped
