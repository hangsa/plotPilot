"""Regex-based single-rule engine for fact_guard (Phase 2A §3).

Loads `config/fact_guard_rules.yaml` and exposes `EngineRule` + `RegexEngine`.
`evaluate_record(record, chapter_text, bible_snapshot=None)` returns `list[GuardHit]`.

Scope (Phase 2A):
- pattern: single regex (Task 3)
- patterns: list[dict(name, regex)] for OR semantics (Task 4)
- python_callable: dotted-path → registered callable (Task 4)
- text_window_chars: chars before/after record.char_position to scan

Python 3.9 compat: `from __future__ import annotations` everywhere.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from application.sf_log.bible_snapshot import ChapterBibleContext
from application.sf_log.callables import resolve_callable
from domain.sf_log.guard_report import GuardHit, Severity
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord


@dataclass
class EngineRule:
    id: str
    applies_to: Optional[SFLogType]  # None = wildcard (Phase 2B Task 5)
    severity: Severity
    description: str
    pattern: Optional[str] = None
    patterns: Optional[list] = None  # NEW (Task 4): list[dict(name, regex)] for OR
    text_window_chars: int = 200
    python_callable: Optional[str] = None  # Phase 2A Task 4 — escape hatch


class RegexEngine:
    """Loads YAML rules + evaluates one record against matching rules.

    Phase 2A Task 4 covers single-pattern, multi-pattern (OR), and python_callable
    rules. Task 5 adds chapter-level dispatch for batched rules like
    location_continuity.
    """

    def __init__(self, rules: Dict[str, EngineRule]) -> None:
        self.rules = rules

    @classmethod
    def from_yaml(cls, path: str) -> "RegexEngine":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        rules: Dict[str, EngineRule] = {}
        for block in data.get("rules", []):
            patterns_raw = block.get("patterns")
            rule = EngineRule(
                id=block["id"],
                applies_to=SFLogType(block["applies_to"]),
                severity=Severity(block["severity"]),
                description=block.get("description", ""),
                pattern=block.get("pattern"),
                patterns=patterns_raw,
                text_window_chars=block.get(
                    "text_window_chars",
                    data.get("defaults", {}).get("text_window_chars", 200),
                ),
                python_callable=block.get("python_callable"),
            )
            rules[rule.id] = rule
        return cls(rules=rules)

    def evaluate_record(
        self,
        record: SFLogRecord,
        chapter_text: str,
        bible_snapshot: Optional[ChapterBibleContext] = None,
    ) -> List[GuardHit]:
        """Evaluate one record against all rules whose applies_to matches.

        bible_snapshot is required for python_callable rules (multi-record rules
        like location_continuity are dispatched at chapter level, see Task 5).
        """
        hits: List[GuardHit] = []
        window = self._text_window(record, chapter_text)
        for rule in self.rules.values():
            # applies_to=None means wildcard — applies to every record log type
            # (Phase 2B Task 5: lets tests build cross-cutting rules without
            # binding to a specific SFLogType).
            if rule.applies_to is not None and rule.applies_to is not record.log_type:
                continue
            # Single regex
            if rule.pattern is not None:
                compiled = re.compile(rule.pattern)
                m = compiled.search(window)
                if m is not None:
                    hits.append(self._hit_from_match(rule, record, m.group(0)))
                continue
            # Multi-pattern (OR semantics — short-circuit on first match)
            if rule.patterns is not None:
                for p in rule.patterns:
                    compiled = re.compile(p["regex"])
                    m = compiled.search(window)
                    if m is not None:
                        hits.append(
                            self._hit_from_match(
                                rule, record, m.group(0), pattern_name=p.get("name")
                            )
                        )
                        break
                continue
            # python_callable
            if rule.python_callable is not None:
                if bible_snapshot is None:
                    continue
                # Multi-record callables (e.g. location_continuity) are dispatched
                # at chapter level — skip them here to avoid signature mismatch.
                if rule.python_callable.endswith("location_continuity.evaluate"):
                    continue
                callable_fn = resolve_callable(rule.python_callable)
                if callable_fn is None:
                    continue
                hits.extend(callable_fn(record, bible_snapshot))
        return hits

    def evaluate_chapter(
        self,
        records: List[SFLogRecord],
        chapter_text: str,
        bible_snapshot: Optional[ChapterBibleContext] = None,
    ) -> List[GuardHit]:
        """Evaluate all records in a chapter; aggregate hits.

        Phase 2A Task 5 — dispatches per-record rules via `evaluate_record`,
        then runs multi-record python_callable rules (currently only
        `location_continuity`) once across the whole record batch.
        """
        hits: List[GuardHit] = []
        for rec in records:
            hits.extend(self.evaluate_record(rec, chapter_text, bible_snapshot))
        # Also dispatch multi-record python_callables (currently only rule 3)
        location_continuity_rule = None
        for rule in self.rules.values():
            if (
                rule.python_callable
                == "application.sf_log.callables.location_continuity.evaluate"
                and bible_snapshot is not None
            ):
                location_continuity_rule = rule
                break
        if location_continuity_rule is not None:
            callable_fn = resolve_callable(
                location_continuity_rule.python_callable  # type: ignore[arg-type]
            )
            if callable_fn is not None:
                hits.extend(callable_fn(records, bible_snapshot))
        return hits

    def _hit_from_match(
        self,
        rule: EngineRule,
        record: SFLogRecord,
        matched: str,
        pattern_name: Optional[str] = None,
    ) -> GuardHit:
        desc = rule.description
        if pattern_name:
            desc = f"{desc} [pattern: {pattern_name}]"
        return GuardHit(
            rule_id=rule.id,
            sflog_id=record.raw,
            severity=rule.severity,
            message=f"{desc} (matched: {matched!r})",
            matched_text=matched,
        )

    def _text_window(self, record: SFLogRecord, chapter_text: str) -> str:
        """Slice chapter_text to ±text_window_chars around record.char_position."""
        applicable_rules = [
            r for r in self.rules.values()
            if r.applies_to is None or r.applies_to is record.log_type
        ]
        if not applicable_rules:
            return chapter_text
        window_size = max(r.text_window_chars for r in applicable_rules)
        start = max(0, record.char_position - window_size)
        end = min(len(chapter_text), record.char_position + window_size)
        return chapter_text[start:end]