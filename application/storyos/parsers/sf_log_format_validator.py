"""SFLogFormatValidator — 严格校验 SFLogRecord 的参数必填规则。"""
from __future__ import annotations

from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.format_error import FormatError
from domain.storyos.value_objects.sf_log import SFLogRecord


# 每类 SF_LOG 的必填参数（spec 附录 A 锁定）
_REQUIRED_PARAMS: dict[SFLogType, frozenset[str]] = {
    SFLogType.CHARACTER_EMOTION: frozenset({"char_id", "emotion"}),
    SFLogType.CHARACTER_RELATION_CHANGE: frozenset({"char_a", "char_b", "type"}),
    SFLogType.CHARACTER_LOCATION_CHANGE: frozenset({"char_id", "location"}),
    SFLogType.CHARACTER_PHYSICAL_CHANGE: frozenset({"char_id", "status"}),
    SFLogType.KNOWLEDGE_GAIN: frozenset({"char_id", "fact"}),
    SFLogType.CONFLICT_ESCALATE: frozenset({"conflict_id", "intensity"}),
    SFLogType.MYSTERY_CLUE: frozenset({"mystery_id", "content"}),
    SFLogType.TWIST_REVEAL: frozenset({"twist_id", "trigger"}),
    SFLogType.EXPECTATION_FULFILL: frozenset({"expectation_id"}),
    SFLogType.GOAL_MILESTONE: frozenset({"goal_id", "marker"}),
    SFLogType.REGISTRY_CREATE: frozenset({"asset_type", "asset_id"}),
}


class SFLogFormatValidator:
    """校验 SFLogRecord 列表，返回 FormatError 列表（无错则空）。"""

    def validate(self, records: list[SFLogRecord]) -> list[FormatError]:
        errors: list[FormatError] = []
        for rec in records:
            required = _REQUIRED_PARAMS.get(rec.log_type, frozenset())
            for key in required:
                if key not in rec.params:
                    errors.append(FormatError(
                        code="MISSING_PARAM",
                        message=f"SFLogType {rec.log_type.value} requires param '{key}'",
                        raw_text=rec.raw,
                        char_position=rec.char_position,
                    ))
                elif not rec.params[key].strip():
                    errors.append(FormatError(
                        code="EMPTY_PARAM",
                        message=f"param '{key}' is empty",
                        raw_text=rec.raw,
                        char_position=rec.char_position,
                    ))
        return errors