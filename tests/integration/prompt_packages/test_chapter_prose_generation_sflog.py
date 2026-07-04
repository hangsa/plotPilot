"""StoryOS 1C D1 — chapter-prose-generation sflog_directive 变量与模板存在性测试。"""
from pathlib import Path

import yaml


PACKAGE_DIR = Path(
    "/Users/longsa/Codes/plotPilot/.claude/worktrees/storyos-1a-foundation/"
    "infrastructure/ai/prompt_packages/nodes/chapter-prose-generation"
)
PKG_YAML = PACKAGE_DIR / "package.yaml"
SFLOG_J2 = PACKAGE_DIR / "sflog_directive.j2"


def test_chapter_prose_generation_has_sflog_directive_variable():
    """spec §3.1: chapter-prose-generation/package.yaml 必须有 sflog_directive 变量。"""
    assert PKG_YAML.exists(), f"Missing: {PKG_YAML}"
    with open(PKG_YAML, encoding="utf-8") as f:
        pkg = yaml.safe_load(f)
    variables = {v["name"] for v in pkg.get("variables", [])}
    assert "sflog_directive" in variables, (
        f"sflog_directive 变量缺失，现有变量: {variables}"
    )


def test_sflog_directive_j2_template_exists():
    """Jinja2 模板存在（spec §3.1 锁定 + 11 类 SF_LOG 示例）。"""
    assert SFLOG_J2.exists(), f"Missing: {SFLOG_J2}"
    content = SFLOG_J2.read_text(encoding="utf-8")
    # 验证 6 类映射（spec §3.3 锁定，会被 evolution_bridge 实际处理）
    required_log_types = [
        "MYSTERY_CLUE",
        "CHARACTER_LOCATION_CHANGE",
        "CHARACTER_PHYSICAL_CHANGE",
        "CHARACTER_RELATION_CHANGE",
        "KNOWLEDGE_GAIN",
        "CONFLICT_ESCALATE",
    ]
    for log_type in required_log_types:
        assert log_type in content, f"{log_type} 示例缺失 in sflog_directive.j2"