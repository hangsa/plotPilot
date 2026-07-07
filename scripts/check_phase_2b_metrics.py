#!/usr/bin/env python3
"""Phase 2B acceptance gate — runs all Phase 2B tests + 2A regression checks.

Mirrors scripts/check_phase_2a_metrics.py (Phase 2A). Exits non-zero on
any failure.
"""
from __future__ import annotations

import subprocess
import sys


PHASE_2B_TESTS = [
    "tests/unit/domain/test_prose_rewrite_value_objects.py",
    "tests/unit/sf_log/test_fact_guard_audit_repository.py",
    "tests/unit/sf_log/test_fact_guard_service_prose_path.py",
    "tests/unit/infrastructure/ai/test_sf_log_prose_rewrite_cpms_node.py",
    "tests/unit/application/sf_log/test_fact_guard_cpms_wiring.py",
    "tests/integration/sf_log/test_prose_rewrite_regression_e2e.py",
    "tests/integration/api/test_chapter_fact_guard_history_endpoint.py",
    "tests/regression/test_phase_2b_prose_rewrite_pass_rate.py",
]

PHASE_2A_REGRESSION_TESTS = [
    "tests/unit/sf_log/test_fact_guard_service.py",
    "tests/regression/test_phase_2a_fact_guard_pass_rate.py",
]


def _run(label: str, cmd: list) -> bool:
    print(f"\n=== {label} ===\n  {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=False)
    return res.returncode == 0


def main() -> int:
    failures = 0

    # Phase 2B
    for t in PHASE_2B_TESTS:
        if not _run(t, ["pytest", t, "-v"]):
            failures += 1

    # 2A regression
    for t in PHASE_2A_REGRESSION_TESTS:
        if not _run(t, ["pytest", t, "-v", "--tb=short"]):
            failures += 1

    # 2B performance
    if not _run(
        "perf", ["pytest", "tests/performance/test_prose_rewrite_latency.py", "-v", "-s"],
    ):
        failures += 1

    print(f"\n{'='*60}\nFAILED: {failures} test files\n{'='*60}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
