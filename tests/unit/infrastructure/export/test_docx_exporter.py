"""DOCX 导出不含 SF_LOG 注释，但含「叙事弧线摘要」附录。"""
from __future__ import annotations

from infrastructure.export.docx_exporter import export_chapter_to_docx


def test_export_strips_sflog_annotations():
    chapter_text = '''
    林远踏入档案室。
    <!-- SF_LOG MYSTERY_CLUE mystery_id="m1" content="blood" -->
    血迹在角落。
    '''
    output = export_chapter_to_docx(chapter_text, project_id="proj-1", chapter=1)
    assert "SF_LOG" not in output.body_text
    assert "MYSTERY_CLUE" not in output.body_text
    assert "林远踏入档案室" in output.body_text
    assert "血迹在角落" in output.body_text


def test_export_includes_narrative_arc_summary():
    chapter_text = "..."
    output = export_chapter_to_docx(chapter_text, project_id="proj-1", chapter=5)
    assert "叙事弧线摘要" in output.appendix_text
    # 含 8 registry 统计
    assert "冲突" in output.appendix_text
    assert "谜题" in output.appendix_text


# ─── Additional coverage (added per code review) ──────────────


def test_export_empty_chapter_text_yields_empty_body():
    """Empty chapter text → empty body_text, but appendix still rendered."""
    output = export_chapter_to_docx("", project_id="proj-1", chapter=1)
    assert output.body_text == ""
    assert "叙事弧线摘要" in output.appendix_text


def test_export_strips_multiple_sflog_blocks_in_one_chapter():
    """Multiple SF_LOG comments in the same chapter all get stripped."""
    chapter_text = (
        '第一节。\n'
        '<!-- SF_LOG CONFLICT_ESCALATE conflict_id="c1" intensity_delta="10" -->\n'
        '第二节。\n'
        '<!-- SF_LOG MYSTERY_CLUE mystery_id="m2" content="x" -->\n'
        '第三节。'
    )
    output = export_chapter_to_docx(chapter_text, project_id="proj-1", chapter=2)
    assert "SF_LOG" not in output.body_text
    assert "CONFLICT_ESCALATE" not in output.body_text
    assert "MYSTERY_CLUE" not in output.body_text
    assert "第一节" in output.body_text
    assert "第二节" in output.body_text
    assert "第三节" in output.body_text


def test_export_leaves_unclosed_html_comment_intact():
    """An unclosed HTML comment (no `-->`) is NOT an SF_LOG marker and
    must pass through unchanged. The regex requires the closing `-->`."""
    chapter_text = '正文。\n<!-- 这不是 SF_LOG，没有关闭\n继续正文。'
    output = export_chapter_to_docx(chapter_text, project_id="proj-1", chapter=1)
    assert "<!-- 这不是 SF_LOG" in output.body_text
    assert "继续正文" in output.body_text


class _FakeProjector:
    """Test double for SnapshotProjector — returns a fixed populated snapshot."""

    def __init__(self, snapshot: dict) -> None:
        self._snapshot = snapshot
        self.calls: list[str] = []

    def project(self, novel_id: str) -> dict:
        self.calls.append(novel_id)
        return self._snapshot


def test_export_renders_real_counts_from_injected_projector():
    """Injecting a fake projector with populated snapshot verifies the
    count formatting path (default SnapshotProjector() yields all-empty
    because no services are wired in unit tests)."""
    fake = _FakeProjector({
        "conflict": {"c1": {}, "c2": {}},
        "mystery": {"m1": {}},
        "foreshadowing": {"f1": {}, "f2": {}, "f3": {}},
        # other 5 registries empty
    })
    output = export_chapter_to_docx(
        "正文", project_id="proj-x", chapter=7, projector=fake,
    )
    assert fake.calls == ["proj-x"]
    assert "- 冲突：2 项" in output.appendix_text
    assert "- 谜题：1 项" in output.appendix_text
    assert "- 伏笔：3 项" in output.appendix_text
    assert "- 反转：无" in output.appendix_text  # empty registry renders as 无


def test_export_survives_projector_exception():
    """If the projector raises, the appendix degrades gracefully and the
    export call still returns a valid ExportResult (body_text intact)."""
    class _Boom:
        def project(self, novel_id: str) -> dict:
            raise RuntimeError("db down")

    output = export_chapter_to_docx(
        "正文", project_id="proj-x", chapter=1, projector=_Boom(),
    )
    assert output.body_text == "正文"
    assert "叙事弧线摘要生成失败" in output.appendix_text
    assert "RuntimeError" in output.appendix_text