"""Integration tests for scripts/migrate_storyos.py CLI (StoryOS Phase 1A Task F2).

Resolves repo root dynamically from __file__ so the tests work both inside the
main checkout and in nested git worktrees (e.g. .claude/worktrees/...).
"""
import subprocess
import sys
from pathlib import Path

# tests/integration/scripts/test_migrate_storyos_cli.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "migrate_storyos.py"


def test_cli_help_exit_zero():
    """python scripts/migrate_storyos.py --help 应退出码 0。"""
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--help"],
        capture_output=True, text=True, cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"--help exited {result.returncode}\nSTDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )


def test_cli_help_shows_subcommands():
    """--help 应显示 dry-run / execute / rollback 三个子命令。"""
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--help"],
        capture_output=True, text=True, cwd=str(_REPO_ROOT),
    )
    assert "dry-run" in result.stdout, result.stdout
    assert "execute" in result.stdout, result.stdout
    assert "rollback" in result.stdout, result.stdout