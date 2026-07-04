"""Frontend chunk-size benchmark - CI gate for storyos bundle budget.

Per plan: storyos-vendor chunk should be < 500KB. Run after `npm run build`:

    cd frontend && npm run build
    python scripts/check_storyos_chunk_size.py

Exit 0 on pass, 1 on fail. Designed to integrate into CI pipeline.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


# Anchor to repo root so the check works regardless of CWD (CI may invoke
# from frontend/ or any subdirectory).
CHUNK_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist" / "assets"
MAX_SIZE_KB = 500


def main() -> int:
    if not CHUNK_DIR.exists():
        print(
            f"[FAIL] {CHUNK_DIR} does not exist. "
            f"Run `cd frontend && npm run build` first.",
            file=sys.stderr,
        )
        return 1

    chunks = [f for f in os.listdir(CHUNK_DIR) if "storyos" in f]
    if not chunks:
        # No storyos chunks after a build is a real regression (route removed,
        # entry tree-shaken away). A CI gate must not green-light that.
        print(
            f"[FAIL] no storyos chunks found in {CHUNK_DIR}. "
            f"Expected at least one storyos-* bundle after build.",
            file=sys.stderr,
        )
        return 1

    failed = False
    for chunk in sorted(chunks):
        size_kb = os.path.getsize(os.path.join(CHUNK_DIR, chunk)) / 1024
        marker = "[FAIL]" if size_kb > MAX_SIZE_KB else "[ OK ]"
        print(f"{marker} {chunk} = {size_kb:.1f}KB (max {MAX_SIZE_KB}KB)")
        if size_kb > MAX_SIZE_KB:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())