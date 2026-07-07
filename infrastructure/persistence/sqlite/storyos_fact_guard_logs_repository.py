"""SQLite repository for storyos_fact_guard_logs — Phase 2B §5."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from application.sf_log.fact_guard_service import FactGuardAction, FactGuardMode


@dataclass(frozen=True)
class FactGuardLogRow:
    chapter_id: int
    chapter_number: int
    novel_id: str
    attempt: int
    mode: "FactGuardMode"
    action: "FactGuardAction"
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