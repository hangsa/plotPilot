"""PredeclaredValidation value object（spec §3.1 Step 3 钩子的返回类型）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class PredeclaredIssueType(str, Enum):
    """validate_predeclared_changes 可能产生的问题类型。"""

    ORPHAN_ASSET = "orphan_asset"
    BLOCKED_STEP = "blocked_step"
    TYPE_MISMATCH = "type_mismatch"
    DEGRADED = "degraded"


@dataclass(frozen=True)
class PredeclaredIssue:
    """单个 predeclared 校验问题。"""

    type: PredeclaredIssueType
    message: str
    asset_id: Optional[str] = None


@dataclass(frozen=True)
class PredeclaredValidation:
    """validate_predeclared_changes 的返回类型（spec §4.1 Step 3）。"""

    valid: bool
    issues: List[PredeclaredIssue] = field(default_factory=list)
