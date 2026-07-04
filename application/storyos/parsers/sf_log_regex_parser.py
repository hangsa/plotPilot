"""SF_LOG 正则解析器（spec 附录 A 完整语法锁定）。

提取章节文本中的 `<!-- SF_LOG <LOG_TYPE> <key>=<value> ... -->` 注释。
"""
from __future__ import annotations

import re

from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.format_error import FormatError
from domain.storyos.value_objects.sf_log import SFLogRecord


# 完整匹配：开始 `<!-- SF_LOG`、类型、空格分隔的 k="v" 对、闭合 `-->`
_SFLOG_PATTERN = re.compile(
    r'<!--\s*SF_LOG\s+(?P<log_type>[A-Z_]+)\s+(?P<params>[^>]*?)\s*-->',
    re.DOTALL,
)
_PARAM_PATTERN = re.compile(r'(?P<key>\w+)\s*=\s*"(?P<value>[^"]*)"')

# 标记 "看起来像 SF_LOG 但没闭合" 的起始模式
_SFLOG_START_PATTERN = re.compile(r'<!--\s*SF_LOG\b')

# 单独资产型 SF_LOG（必含 asset_id）；关系型 / registry-create 无 asset_id
_SINGLE_ASSET_PARAM_KEYS = {
    SFLogType.MYSTERY_CLUE: "mystery_id",
    SFLogType.CONFLICT_ESCALATE: "conflict_id",
    SFLogType.TWIST_REVEAL: "twist_id",
    SFLogType.EXPECTATION_FULFILL: "expectation_id",
    SFLogType.GOAL_MILESTONE: "goal_id",
    SFLogType.CHARACTER_EMOTION: "char_id",
    SFLogType.CHARACTER_LOCATION_CHANGE: "char_id",
    SFLogType.CHARACTER_PHYSICAL_CHANGE: "char_id",
    SFLogType.KNOWLEDGE_GAIN: "char_id",
}


class SFLogRegexParser:
    """零 LLM SF_LOG 解析器（纯正则）。"""

    def parse(self, text: str, chapter_id: int) -> list[SFLogRecord]:
        """从章节文本中提取所有 SFLogRecord。

        Args:
            text: 章节纯文本
            chapter_id: 章节号（≥1）

        Returns:
            SFLogRecord 列表（按文本出现顺序）

        Raises:
            FormatError: 遇到语法错误（缺闭合、类型未知等）
        """
        results: list[SFLogRecord] = []
        for match in _SFLOG_PATTERN.finditer(text):
            log_type_str = match.group("log_type")
            try:
                log_type = SFLogType(log_type_str.lower())
            except ValueError:
                raise FormatError(
                    code="UNKNOWN_LOG_TYPE",
                    message=f"Unknown SFLogType: {log_type_str}",
                    raw_text=match.group(0),
                    char_position=match.start(),
                )
            params = {
                m.group("key"): m.group("value")
                for m in _PARAM_PATTERN.finditer(match.group("params"))
            }
            asset_id = self._extract_asset_id(log_type, params)
            results.append(
                SFLogRecord(
                    log_type=log_type,
                    params=params,
                    raw=match.group(0),
                    chapter_id=chapter_id,
                    char_position=match.start(),
                    asset_id=asset_id,
                )
            )

        # 单独检测 "看起来像 SF_LOG 但没闭合" 的标签 → 抛 FormatError
        self._detect_malformed_tags(text)

        return results

    def _extract_asset_id(
        self, log_type: SFLogType, params: dict[str, str],
    ) -> str | None:
        """单资产型提取 asset_id；关系型 / registry-create 返回 None。"""
        key = _SINGLE_ASSET_PARAM_KEYS.get(log_type)
        if key is None:
            return None
        return params.get(key)

    def _detect_malformed_tags(self, text: str) -> None:
        """检测 `<!-- SF_LOG ...` 开头但缺少 `-->` 闭合的损坏标签。

        主正则要求 `-->` 收尾，因此无法匹配未闭合的标签。我们另外扫一遍
        起始位置，检查其后的合理窗口（避免与下一个 SF_LOG 的起始混淆），
        若未找到 `-->`，则视作格式错误。
        """
        # 构造已成功匹配的 SF_LOG 起始集合（这些是合法的，不算 malformed）
        valid_starts = {m.start() for m in _SFLOG_PATTERN.finditer(text)}

        for start_match in _SFLOG_START_PATTERN.finditer(text):
            start = start_match.start()
            if start in valid_starts:
                # 这个起始已经被主正则匹配为合法标签，跳过
                # 但要确认：需要从 "下一个" 标签的起始处判断
                # 由于合法标签的 start 也在 valid_starts 中，
                # 我们对每个 _SFLOG_START_PATTERN 匹配都检查它是否对应
                # 一个合法完整标签。简单做法：检查 start 之后能否找到 `-->`
                continue

            # 未被主正则识别为合法起始 → 找 `-->`
            # 合理窗口：限定到下一个可能的 `<!--` 之前
            next_open = text.find('<!--', start + 1)
            search_end = next_open if next_open != -1 else start + 5000
            window = text[start:search_end]
            if '-->' not in window:
                raise FormatError(
                    code="MALFORMED_TAG",
                    message="SF_LOG tag is missing closing '-->'",
                    raw_text=text[start:search_end].rstrip(),
                    char_position=start,
                )