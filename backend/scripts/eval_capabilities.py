#!/usr/bin/env python3
"""L0 capability-eval CLI: coverage and schema validation. No model, no network."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.application.capabilities.registry import FROZEN_CAPABILITY_IDS  # noqa: E402
from app.application.services.capability_eval import (  # noqa: E402
    CapabilityEvalError,
    load_suite,
    run_l0_suite,
    validate_suite_coverage,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate L0 capability golden sets.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate schema + coverage and exit 0/1",
    )
    parser.add_argument(
        "--golden-dir",
        type=Path,
        default=None,
        help="override golden directory",
    )
    args = parser.parse_args(argv)
    try:
        cases = load_suite(args.golden_dir)
        validate_suite_coverage(cases)
        results = run_l0_suite(args.golden_dir)
    except CapabilityEvalError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"capabilities: {len(FROZEN_CAPABILITY_IDS)}")
    print(f"cases: {len(cases)}")
    print(f"l0_status: all {len(results)} data_registered")
    by_cap: dict[str, int] = {}
    for case in cases:
        by_cap[case.capability_id] = by_cap.get(case.capability_id, 0) + 1
    for capability_id in FROZEN_CAPABILITY_IDS:
        print(f"  {capability_id}: {by_cap.get(capability_id, 0)}")
    if args.check:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
