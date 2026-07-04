"""DOCX export — strip SF_LOG annotations + append narrative-arc summary.

1D scope: produces a text body + appendix pair suitable for assembling
into a DOCX (the actual .docx byte assembly is out of scope; that's a
separate task using python-docx or similar).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from application.storyos.services.snapshot_projector import SnapshotProjector

# Match HTML comments containing SF_LOG markers (same regex shape as
# frontend SFLogInspector.vue for symmetry — backend regex is DOTALL so
# multi-line SF_LOG blocks are caught).
_SFLOG_PATTERN = re.compile(r"<!--\s*SF_LOG[^>]*?-->", re.DOTALL)

# Chinese display names for the 8 registries, used in the narrative arc
# summary appendix. Order matches SnapshotProjector._services keys.
_REGISTRY_LABELS_ZH = {
    "conflict": "冲突",
    "mystery": "谜题",
    "twist": "反转",
    "promise": "承诺",
    "reveal": "揭示",
    "expectation": "预期",
    "goal": "目标",
    "foreshadowing": "伏笔",
}


@dataclass
class ExportResult:
    """Lightweight container for DOCX export pieces. Frontend/tests can
    inspect body_text and appendix_text directly without parsing DOCX."""

    body_text: str
    appendix_text: str


def _build_arc_summary(project_id: str) -> str:
    """Use SnapshotProjector to count active assets per registry, then
    format as Chinese-labeled bullet list. Empty registries render as
    "无" (none) so the appendix is never empty.
    """
    snap = SnapshotProjector().project(project_id)
    lines: list = []
    for registry_key, label in _REGISTRY_LABELS_ZH.items():
        registry_assets = snap.get(registry_key, {})
        count = len(registry_assets) if isinstance(registry_assets, dict) else 0
        lines.append(f"- {label}：{count} 项" if count else f"- {label}：无")
    return "\n".join(lines)


def export_chapter_to_docx(
    chapter_text: str,
    project_id: str,
    chapter: int,
) -> ExportResult:
    """Strip SF_LOG annotations from chapter body and append a narrative
    arc summary derived from the project snapshot.
    """
    body_text = _SFLOG_PATTERN.sub("", chapter_text)
    summary = _build_arc_summary(project_id)
    appendix_text = f"叙事弧线摘要（第 {chapter} 章）\n\n{summary}"
    return ExportResult(body_text=body_text, appendix_text=appendix_text)
