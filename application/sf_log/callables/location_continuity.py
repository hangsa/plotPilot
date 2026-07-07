"""Rule 3 — character_location.continuity (Phase 2A §4 table).

HARD hit if two consecutive CHARACTER_LOCATION_CHANGE records (same character_id)
land in locations not connected via bible.worldbuilding_links.

Phase 2A simplified: presence of any 'to' value not reachable from previous 'to'
within 2-hop graph triggers HARD. Empty links → no check (passthrough).
"""
from __future__ import annotations

from application.sf_log.bible_snapshot import ChapterBibleContext
from domain.sf_log.guard_report import GuardHit, Severity
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord


def _reachable(links: dict, src: str, dst: str) -> bool:
    """BFS up to depth 2 — return True if dst reachable from src."""
    if src == dst:
        return True
    visited = {src}
    frontier = [src]
    for _ in range(2):
        next_frontier = []
        for node in frontier:
            for neighbor in links.get(node, []):
                if neighbor == dst:
                    return True
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.append(neighbor)
        frontier = next_frontier
    return False


def evaluate(records: list, bible: ChapterBibleContext) -> list[GuardHit]:
    if not bible.worldbuilding_links:
        return []  # no link graph defined → rule not enforceable

    hits = []
    by_char: dict = {}
    for rec in records:
        if rec.log_type is not SFLogType.CHARACTER_LOCATION_CHANGE:
            continue
        char_id = rec.params.get("character_id")
        to = rec.params.get("to")
        if char_id is None or to is None:
            continue
        prev_to = by_char.get(char_id, [None])[-1]
        if prev_to is not None and not _reachable(bible.worldbuilding_links, prev_to, to):
            hits.append(
                GuardHit(
                    rule_id="character_location.continuity",
                    sflog_id=rec.raw,
                    severity=Severity.HARD,
                    message=f"角色 '{char_id}' 从 '{prev_to}' 到 '{to}' 不连通（bible.links 缺边）",
                )
            )
        by_char.setdefault(char_id, []).append(to)
    return hits