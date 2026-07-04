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
# frontend SFLogInspector.vue for symmetry). DOTALL is defensive: in
# practice `[^>]` already excludes newlines embedded inside the comment,
# but if a future SF_LOG marker spans lines we still want to strip it.
_SFLOG_PATTERN = re.compile(r"<!--\s*SF_LOG[^>]*?-->", re.DOTALL)

# i18n: ZH-only per 1D spec (叙事弧线摘要). Future E2 task may add en-US.
# Order matches SnapshotProjector._services keys.
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


@dataclass(frozen=True)
class ExportResult:
    """Lightweight container for DOCX export pieces. Frontend/tests can
    inspect body_text and appendix_text directly without parsing DOCX."""

    body_text: str
    appendix_text: str


def _build_arc_summary(project_id: str, projector: SnapshotProjector | None = None) -> str:
    """Use SnapshotProjector to count active assets per registry, then
    format as Chinese-labeled bullet list. Empty registries render as
    "无" (none) so the appendix is never empty. On projector failure
    (DB error, missing table) returns a degraded summary so the export
    call still succeeds.
    """
    p = projector if projector is not None else SnapshotProjector()
    try:
        snap = p.project(project_id)
    except Exception as exc:
        return f"叙事弧线摘要生成失败：{type(exc).__name__}: {exc}"

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
    projector: SnapshotProjector | None = None,
) -> ExportResult:
    """Strip SF_LOG annotations from chapter body and append a narrative
    arc summary derived from the project snapshot.

    `projector` is an optional injection seam: tests pass a fake projector
    with a populated snapshot to verify count rendering; production
    callers leave it None to use the default SnapshotProjector() (which
    requires all 8 registry services to be wired at app startup).
    """
    body_text = _SFLOG_PATTERN.sub("", chapter_text)
    summary = _build_arc_summary(project_id, projector)
    appendix_text = f"叙事弧线摘要（第 {chapter} 章）\n\n{summary}"
    return ExportResult(body_text=body_text, appendix_text=appendix_text)