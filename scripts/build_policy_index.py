"""Build the deterministic local policy index from the approved PDF."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from app.policy.source import DEFAULT_POLICY_INDEX, DEFAULT_POLICY_PDF, build_policy_index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the local read-only store-policy index.")
    parser.add_argument("--input", type=Path, default=Path(os.environ.get("EMPORIO_POLICY_PDF", str(DEFAULT_POLICY_PDF))))
    parser.add_argument("--output", type=Path, default=DEFAULT_POLICY_INDEX)
    args = parser.parse_args(argv)
    report = build_policy_index(input_path=args.input, output=args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
