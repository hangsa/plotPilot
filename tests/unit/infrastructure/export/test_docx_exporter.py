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
