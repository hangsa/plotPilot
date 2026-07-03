"""StoryOS 数据迁移 CLI（1A 脚手架，1E 补完业务逻辑）。

子命令：
    dry-run    扫描 + 报告，不写入
    execute    实际迁移（带断点续跑）
    rollback   回滚（基于迁移日志）

Usage:
    python scripts/migrate_storyos.py dry-run
    python scripts/migrate_storyos.py execute
    python scripts/migrate_storyos.py rollback --to <migration_id>
"""
from __future__ import annotations

import argparse
import sys


def cmd_dry_run(args) -> int:
    raise NotImplementedError("完整实现在 Phase 1E")


def cmd_execute(args) -> int:
    raise NotImplementedError("完整实现在 Phase 1E")


def cmd_rollback(args) -> int:
    raise NotImplementedError("完整实现在 Phase 1E")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="migrate_storyos",
        description="StoryOS 数据迁移 CLI（1A 脚手架，1E 补完业务逻辑）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_dry = sub.add_parser("dry-run", help="扫描 + 报告，不写入")
    p_dry.set_defaults(func=cmd_dry_run)

    p_exec = sub.add_parser("execute", help="实际迁移（带断点续跑）")
    p_exec.set_defaults(func=cmd_execute)

    p_rb = sub.add_parser("rollback", help="回滚（基于迁移日志）")
    p_rb.add_argument("--to", required=True, help="回滚到指定 migration_id")
    p_rb.set_defaults(func=cmd_rollback)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())