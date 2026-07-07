"""StoryOS 1C D1 — ProseComposer 链路中 sflog_directive 变量的形状契约测试。"""
from pathlib import Path

import yaml


PKG_YAML = Path(
    "/Users/longsa/Codes/plotPilot/.claude/worktrees/storyos-1a-foundation/"
    "infrastructure/ai/prompt_packages/nodes/chapter-prose-generation/package.yaml"
)


def test_prose_composer_sflog_directive_variable_default_is_empty_string():
    """sflog_directive 应为 string 类型且 default 为 ''（由 1D/StoryOSDelegate 在 Step 1 注入）。"""
    with open(PKG_YAML, encoding="utf-8") as f:
        pkg = yaml.safe_load(f)
    sflog_var = next(
        (v for v in pkg["variables"] if v["name"] == "sflog_directive"),
        None,
    )
    assert sflog_var is not None, "sflog_directive 变量缺失"
    assert sflog_var["type"] == "string"
    assert sflog_var["default"] == ""


def test_build_variables_includes_rendered_sflog_directive():
    """_build_variables 必须把 sflog_directive.j2 渲染结果塞进 explicit_variables。

    目的：阻止 future regression 把 sflog_directive 变量从 _build_variables 误删。
    验证 6 类映射 SF_LOG 都出现在渲染结果中（spec §3.3 锁定）。
    """
    from engine.pipeline.prose_composer import (
        ChapterProseInvocationComposer,
        ProseCompositionRequest,
    )

    composer = ChapterProseInvocationComposer()
    request = ProseCompositionRequest(
        novel_id="n-1",
        chapter_number=1,
        outline="测试章节大纲",
        context_text="连续性上下文",
    )
    variables = composer._build_variables(request)

    assert "sflog_directive" in variables, (
        "sflog_directive 键缺失 — LLM 看不到 SF_LOG 语法"
    )
    rendered = variables["sflog_directive"]
    assert rendered, "sflog_directive 渲染结果为空"

    for log_type in (
        "MYSTERY_CLUE",
        "CHARACTER_LOCATION_CHANGE",
        "CHARACTER_PHYSICAL_CHANGE",
        "CHARACTER_RELATION_CHANGE",
        "KNOWLEDGE_GAIN",
        "CONFLICT_ESCALATE",
    ):
        assert log_type in rendered, f"{log_type} 缺失 in rendered sflog_directive"

    assert "{{ predeclared_changes }}" not in rendered, (
        "Jinja2 占位符未替换 — predeclared_changes 变量名错"
    )


def test_build_variables_sflog_directive_passes_metadata_summary():
    """metadata.storyos_predeclared_summary 透传到 SF_LOG 指令块底部。"""
    from engine.pipeline.prose_composer import (
        ChapterProseInvocationComposer,
        ProseCompositionRequest,
    )

    composer = ChapterProseInvocationComposer()
    request = ProseCompositionRequest(
        novel_id="n-1",
        chapter_number=1,
        outline="测试大纲",
        context_text="",
        metadata={
            "storyos_predeclared_summary": (
                "MUST_EMIT: MYSTERY_CLUE mystery_id=m1 content='blood'"
            ),
        },
    )
    variables = composer._build_variables(request)

    assert "MUST_EMIT: MYSTERY_CLUE" in variables["sflog_directive"], (
        "metadata.storyos_predeclared_summary 未透传到 sflog_directive 渲染"
    )