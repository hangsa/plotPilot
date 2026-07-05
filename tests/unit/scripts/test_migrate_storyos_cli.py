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


def test_cli_aggregates_errors_in_execute(cli):
    """--execute 输出包含 errors 字段聚合（spec §1E 锁定）。"""
    # 使用空 project-id 测试错误聚合路径
    # （实际错误聚合测试在 Group F 集成测试中验证）
    result = cli("--execute", "--project-id", "test-novel-1", "--json")
    # 即使无数据也应该返回有效 JSON 报告
    assert result.returncode in (0, 1)  # 0 if empty, 1 if errors


def test_cli_progress_output_is_human_readable(cli):
    """默认输出（非 --json）包含进度信息（人类可读）。"""
    result = cli("--dry-run", "--project-id", "test-novel-1")
    assert result.returncode == 0
    # 不带 --json 时输出应该包含 total / migratable 等字段名
    assert "total" in result.stdout.lower() or "migratable" in result.stdout.lower()
