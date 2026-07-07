"""CPMS node loader tests for sf-log-prose-rewrite (Phase 2B Task 4)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


NODE_DIR = (
    Path(__file__).resolve().parents[4]
    / "infrastructure" / "ai" / "prompt_packages" / "nodes" / "sf-log-prose-rewrite"
)


class TestPackageManifest:
    @pytest.fixture
    def manifest(self):
        with open(NODE_DIR / "package.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_required_keys(self, manifest):
        for key in ("name", "category", "id", "sort_order", "tags", "variables", "builtin"):
            assert key in manifest

    def test_id_matches(self, manifest):
        assert manifest["id"] == "sf-log-prose-rewrite"

    def test_sort_order_unique(self, manifest):
        assert manifest["sort_order"] == 116

    def test_builtin(self, manifest):
        assert manifest["builtin"] is True

    def test_required_variables(self, manifest):
        var_names = {v["name"] for v in manifest["variables"]}
        assert var_names >= {"chapter_text", "hits", "sflog_records", "attempt"}

    def test_variable_required_flags(self, manifest):
        for var in manifest["variables"]:
            if var["name"] in ("chapter_text", "hits", "sflog_records", "attempt"):
                assert var.get("required", False) is True


class TestUserTemplate:
    def test_user_md_exists(self):
        assert (NODE_DIR / "user.md").exists()

    def test_user_md_has_required_placeholders(self):
        text = (NODE_DIR / "user.md").read_text(encoding="utf-8")
        for placeholder in ("{{chapter_text}}", "{{hits}}", "{{sflog_records}}", "{{attempt}}"):
            assert placeholder in text, f"missing {placeholder}"

    def test_user_md_no_prose_body_constraint_violation(self):
        """The prose node MUST allow prose editing — verify it does NOT
        contain the same prose-body-prohibition text as sflog node."""
        text = (NODE_DIR / "user.md").read_text(encoding="utf-8")
        sflog_text = (
            Path(__file__).resolve().parents[4]
            / "infrastructure" / "ai" / "prompt_packages" / "nodes"
            / "sf-log-rewrite-with-hints" / "user.md"
        ).read_text(encoding="utf-8")
        assert "严禁修改 prose body" in sflog_text
        # The new prose node should *not* contain that exact sentence
        assert "严禁修改 prose body" not in text

    def test_rollback_signal_in_user_md(self):
        text = (NODE_DIR / "user.md").read_text(encoding="utf-8")
        assert "REQUIRES_PROSE_ROLLBACK" in text
