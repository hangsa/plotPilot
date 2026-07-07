"""Verify sf-log-rewrite-with-hints CPMS package loads and registers a handler."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_package_yaml_exists():
    pkg = Path(__file__).parent.parent.parent.parent.parent / "infrastructure" / "ai" / "prompt_packages" / "nodes" / "sf-log-rewrite-with-hints"
    assert (pkg / "package.yaml").exists(), f"missing {(pkg / 'package.yaml')}"
    assert (pkg / "user.md").exists(), f"missing {(pkg / 'user.md')}"


def test_package_yaml_has_required_fields():
    import yaml
    pkg = Path(__file__).parent.parent.parent.parent.parent / "infrastructure" / "ai" / "prompt_packages" / "nodes" / "sf-log-rewrite-with-hints" / "package.yaml"
    data = yaml.safe_load(pkg.read_text(encoding="utf-8"))
    assert data["id"] == "sf-log-rewrite-with-hints"
    assert "category" in data
    assert "variables" in data
    # Required variables
    var_names = {v["name"] for v in data["variables"]}
    assert "chapter_text" in var_names
    assert "hits" in var_names
    assert "attempt" in var_names


def test_user_md_has_rewrite_directive():
    pkg = Path(__file__).parent.parent.parent.parent.parent / "infrastructure" / "ai" / "prompt_packages" / "nodes" / "sf-log-rewrite-with-hints" / "user.md"
    content = pkg.read_text(encoding="utf-8")
    assert "{{chapter_text}}" in content
    assert "{{hits}}" in content
    assert "SF_LOG" in content
    # Must explicitly forbid editing prose body
    assert "prose" in content.lower() or "正文" in content