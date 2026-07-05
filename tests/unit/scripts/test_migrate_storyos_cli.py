"""CLI 单元测试（通过 subprocess 调用）。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Path-agnostic: tests live at tests/unit/scripts/, parents[3] is repo root.
CLI_PATH = Path(__file__).resolve().parents[3] / "scripts" / "migrate_storyos.py"
REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def cli():
    """Subprocess 调用 CLI（隔离环境，不污染主进程）。"""
    def run(*args, env_extra=None):
        env = {"PYTHONPATH": str(REPO_ROOT)}
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, str(CLI_PATH), *args],
            capture_output=True, text=True, env=env, timeout=30,
        )
    return run


def test_cli_help_shows_subcommands(cli):
    result = cli("--help")
    assert result.returncode == 0
    assert "--dry-run" in result.stdout
    assert "--execute" in result.stdout
    assert "--rollback" in result.stdout


def test_cli_dry_run_outputs_json_report(cli):
    """--dry-run 输出 JSON 报告到 stdout。"""
    result = cli("--dry-run", "--project-id", "test-novel-1", "--json")
    # 即使数据库无数据，dry-run 应该返回有效 JSON
    assert result.returncode == 0, f"stderr: {result.stderr}"
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"stdout 不是 JSON: {result.stdout}")
    assert "total" in report
    assert "migratable" in report


def test_cli_execute_requires_project_id(cli):
    """--execute 必须指定 --project-id。"""
    result = cli("--execute")
    assert result.returncode != 0
    assert "project-id" in result.stderr.lower() or "project_id" in result.stderr.lower()


def test_cli_batch_size_argument_parsed(cli):
    """--batch-size 参数被正确解析。"""
    result = cli(
        "--dry-run", "--project-id", "test-novel-1",
        "--batch-size", "100", "--json",
    )
    assert result.returncode == 0


def test_cli_invalid_subcommand_shows_error(cli):
    result = cli("--invalid-flag")
    assert result.returncode != 0


def test_cli_no_args_shows_usage(cli):
    """无参数时显示 usage。"""
    result = cli()
    assert "--dry-run" in result.stdout or "--execute" in result.stdout or "usage" in result.stdout.lower()
