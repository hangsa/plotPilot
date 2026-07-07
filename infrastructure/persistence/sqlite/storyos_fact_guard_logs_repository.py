"""SQLite repository for storyos_fact_guard_logs — Phase 2B §5."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class FactGuardLogRow:
    chapter_id: int
    chapter_number: int
    novel_id: str
    attempt: int
    mode: str                          # 'sflog' | 'prose'
    action: str
    hard_before: int = 0
    hard_after: int = 0
    rule_id: Optional[str] = None
    severity: Optional[str] = None
    diff_excerpt: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class FactGuardLogPage:
    rows: List[dict] = field(default_factory=list)
    total: int = 0