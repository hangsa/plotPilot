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