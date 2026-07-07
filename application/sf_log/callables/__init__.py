"""python_callable registry for fact_guard rules (Phase 2A §3 escape hatch).

Each callable signature:
- Single-record: `callable(record: SFLogRecord, bible: ChapterBibleContext) -> list[GuardHit]`
- Multi-record (only location_continuity): `callable(records: list[SFLogRecord], bible) -> list[GuardHit]`

Rule → callable mapping is determined by `python_callable` string in YAML:
  python_callable: "application.sf_log.callables.location_continuity.evaluate"
"""
from __future__ import annotations

from application.sf_log.bible_snapshot import ChapterBibleContext
from application.sf_log.callables.conflict_escalate_repeat import evaluate as _conflict_eval  # noqa: F401
from application.sf_log.callables.goal_milestone_skip import evaluate as _goal_eval  # noqa: F401
from application.sf_log.callables.knowledge_omniscience import evaluate as _knowledge_eval  # noqa: F401
from application.sf_log.callables.location_continuity import evaluate as _location_eval  # noqa: F401
from application.sf_log.callables.mystery_reveal_window import evaluate as _mystery_eval  # noqa: F401
from application.sf_log.callables.relation_no_self_loop import evaluate as _relation_eval  # noqa: F401
from domain.sf_log.guard_report import GuardHit, Severity


# Public aliases used by tests + rule YAML
CONFLICT_ESCALATE_REPEAT = _conflict_eval
GOAL_MILESTONE_SKIP = _goal_eval
KNOWLEDGE_OMNISCIENCE = _knowledge_eval
LOCATION_CONTINUITY = _location_eval
MYSTERY_REVEAL_WINDOW = _mystery_eval
RELATION_NO_SELF_LOOP = _relation_eval


# Registry: python_callable string → callable
_CALLABLE_REGISTRY = {
    "application.sf_log.callables.relation_no_self_loop.evaluate": _relation_eval,
    "application.sf_log.callables.knowledge_omniscience.evaluate": _knowledge_eval,
    "application.sf_log.callables.location_continuity.evaluate": _location_eval,
    "application.sf_log.callables.mystery_reveal_window.evaluate": _mystery_eval,
    "application.sf_log.callables.conflict_escalate_repeat.evaluate": _conflict_eval,
    "application.sf_log.callables.goal_milestone_skip.evaluate": _goal_eval,
}


def resolve_callable(python_callable: str):
    """Resolve YAML python_callable string to actual Python callable.

    Returns None if module path doesn't match registry (Phase 2A fail-soft:
    engine treats unknown callable as 'rule disabled').
    """
    return _CALLABLE_REGISTRY.get(python_callable)