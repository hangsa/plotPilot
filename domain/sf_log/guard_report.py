"""GuardReport + GuardHit + Severity (Phase 2A spec §2).

Frozen dataclasses — pydantic is used elsewhere; here we keep dataclass for
simpler interop with `python_callable` signatures and avoid BaseModel overhead.

Python 3.9 compat: `from __future__ import annotations` defers evaluation of
`list[GuardHit]` so this file works on 3.9 without runtime annotations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Severity(str, Enum):
    """规则命中严重度（HARD = must-pass；SOFT = warn-only）。"""

    HARD = "hard"
    SOFT = "soft"


@dataclass(frozen=True)
class GuardHit:
    """单条 fact_guard 命中。"""

    rule_id: str
    sflog_id: Optional[str]
    severity: Severity
    message: str
    matched_text: Optional[str] = None


@dataclass
class GuardReport:
    """单章 fact_guard 评估报告。"""

    passed: bool
    forced_pass: bool
    attempt: int
    hits: List[GuardHit] = field(default_factory=list)

    def hard_hits(self) -> List[GuardHit]:
        return [h for h in self.hits if h.severity is Severity.HARD]