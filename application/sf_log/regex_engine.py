"""Regex-based single-rule engine for fact_guard (Phase 2A §3).

Loads `config/fact_guard_rules.yaml` and exposes `EngineRule` + `RegexEngine`.
`evaluate_record(record, chapter_text)` returns `list[GuardHit]`.

Scope (Phase 2A):
- pattern: single regex (multi-pattern + python_callable added in Task 4/5)
- text_window_chars: chars before/after record.char_position to scan

Python 3.9 compat: `from __future__ import annotations` everywhere.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from domain.sf_log.guard_report import GuardHit, Severity
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord


@dataclass
class EngineRule:
    id: str
    applies_to: SFLogType
    severity: Severity
    description: str
    pattern: Optional[str] = None
    text_window_chars: int = 200
    python_callable: Optional[str] = None  # Phase 2A Task 4 — escape hatch


class RegexEngine:
    """Loads YAML rules + evaluates one record against matching rules.

    Phase 2A Task 3 covers pattern-only rules. Task 4/5 add multi-pattern +
    python_callable + chapter-level dispatch.
    """

    def __init__(self, rules: Dict[str, EngineRule]) -> None:
        self.rules = rules

    @classmethod
    def from_yaml(cls, path: str) -> "RegexEngine":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        rules: Dict[str, EngineRule] = {}
        for block in data.get("rules", []):
            rule = EngineRule(
                id=block["id"],
                applies_to=SFLogType(block["applies_to"]),
                severity=Severity(block["severity"]),
                description=block.get("description", ""),
                pattern=block.get("pattern"),
                text_window_chars=block.get(
                    "text_window_chars",
                    data.get("defaults", {}).get("text_window_chars", 200),
                ),
                python_callable=block.get("python_callable"),
            )
            rules[rule.id] = rule
        return cls(rules=rules)

    def evaluate_record(
        self, record: SFLogRecord, chapter_text: str
    ) -> List[GuardHit]:
        """Evaluate one record against all rules whose applies_to matches."""
        hits: List[GuardHit] = []
        window = self._text_window(record, chapter_text)
        for rule in self.rules.values():
            if rule.applies_to is not record.log_type:
                continue
            if rule.pattern is None:
                continue  # python_callable rules handled in Task 4
            compiled = re.compile(rule.pattern)
            m = compiled.search(window)
            if m is None:
                continue
            hits.append(
                GuardHit(
                    rule_id=rule.id,
                    sflog_id=record.raw,
                    severity=rule.severity,
                    message=f"{rule.description} (matched: {m.group(0)!r})",
                    matched_text=m.group(0),
                )
            )
        return hits

    def _text_window(self, record: SFLogRecord, chapter_text: str) -> str:
        """Slice chapter_text to ±text_window_chars around record.char_position."""
        applicable_rules = [r for r in self.rules.values() if r.applies_to is record.log_type]
        if not applicable_rules:
            return chapter_text
        window_size = max(r.text_window_chars for r in applicable_rules)
        start = max(0, record.char_position - window_size)
        end = min(len(chapter_text), record.char_position + window_size)
        return chapter_text[start:end]
