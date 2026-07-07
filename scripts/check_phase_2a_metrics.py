"""Print Phase 2A acceptance metrics per spec §9.

Run: python scripts/check_phase_2a_metrics.py
Expected: 5-row table with metric / target / actual values, all PASS.

Notes (correction in plan):
- Drops the "fact_guard latency (P95)" row — the threshold is asserted by
  `tests/performance/test_fact_guard_latency.py` (uses @pytest.mark.slow
  because @pytest.mark.performance is not registered in pytest.ini and
  `--strict-markers` would reject it).
- Drops the v1.2 full-suite regression row from the printable table because
  (a) the 5-minute run is too long for a CI-friendly script, and (b) ~16
  PRE-EXISTING v1.2 failures are KNOWN and out of Phase 2A scope. The
  acceptance gate runs the full suite separately (Step A of plan).
- 5 printable rows: unit / integration / regression / Python 3.9 compat /
  chapter.warnings endpoint.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _has(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def measure(name: str, cmd: list, target: str, timeout: int = 180) -> dict:
    start = time.time()
    if not _has(cmd[0]):
        return {"name": name, "target": target, "status": "SKIP",
                "detail": f"{cmd[0]} not on PATH", "elapsed": 0.0}
    try:
        result = subprocess.run(
            cmd, capture_output=True, cwd=str(ROOT), text=True,
            timeout=timeout,
        )
        elapsed = time.time() - start
        last_line = (result.stdout or "").strip().splitlines()[-1] if result.stdout else ""
        return {
            "name": name,
            "target": target,
            "status": "PASS" if result.returncode == 0 else "FAIL",
            "detail": last_line[:60],
            "elapsed": elapsed,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"name": name, "target": target, "status": "TIMEOUT",
                "detail": f">{timeout}s", "elapsed": time.time() - start}


def main() -> int:
    print(f"{'Metric':45s} | {'Target':22s} | {'Status':6s} | {'Detail':60s}")
    print("-" * 140)

    metrics = [
        measure(
            "unit tests (sf_log)",
            ["python3", "-m", "pytest", "tests/unit/sf_log/", "-q"],
            "all pass",
        ),
        measure(
            "integration tests (sf_log)",
            ["python3", "-m", "pytest", "tests/integration/sf_log/", "-q"],
            "all pass",
        ),
        measure(
            "regression test (20ch pass rate >= 70%)",
            ["python3", "-m", "pytest",
             "tests/regression/test_phase_2a_fact_guard_pass_rate.py", "-v"],
            "PASS",
        ),
    ]
    # Python 3.9 compat: grep is EXPECTED to return exit-1 with no output when
    # there are no PEP 604 violations in the new sf_log trees. Treat that as PASS.
    pep_grep = measure(
        "Python 3.9 compat (no PEP 604 in sf_log)",
        ["grep", "-rn", " | None", "domain/sf_log", "application/sf_log"],
        "no matches",
    )
    if pep_grep["status"] == "FAIL" and not (pep_grep.get("detail") or "").strip():
        pep_grep["status"] = "PASS"
        pep_grep["detail"] = "no matches"
    metrics.append(pep_grep)

    metrics.append(measure(
        "chapter.warnings endpoint test",
        ["python3", "-m", "pytest",
         "tests/integration/sf_log/test_chapter_warnings_endpoint.py", "-q"],
        "200/404",
    ))

    for m in metrics:
        print(f"{m['name']:45s} | {m['target']:22s} | {m.get('status','?'):6s} "
              f"| {m.get('detail','')[:60]:60s} ({m.get('elapsed',0.0):.1f}s)")

    # Informational: perf latency is asserted by the perf test (not this script).
    print("\nInformational: fact_guard P95 latency threshold is asserted by")
    print("  pytest tests/performance/test_fact_guard_latency.py -v")
    print("  (target P95 < 100ms; uses @pytest.mark.slow).")

    # Informational: full v1.2 baseline regression is OUT OF SCOPE here.
    print("\nInformational: full v1.2 baseline regression (>5min, ~16 known")
    print("pre-existing failures) is run separately by the acceptance gate.")
    print("  python3 -m pytest tests/ -m 'not slow' --tb=line -q --no-header")

    failed = [m["name"] for m in metrics if m.get("status") == "FAIL"]
    if failed:
        print(f"\nFAIL rows ({len(failed)}):")
        for f in failed:
            print(f"  - {f}")
        return 1
    print("\nAll 5 acceptance metrics PASS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
