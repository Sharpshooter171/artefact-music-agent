from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.catalog.importer import build_catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the local read-only SQLite catalog from supplied CSVs."
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/generated/catalog.sqlite"),
    )
    args = parser.parse_args(argv)

    report = build_catalog(data_dir=args.data_dir, output=args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
