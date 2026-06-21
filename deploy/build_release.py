#!/usr/bin/env python3
"""Build a server-only deployment tarball with no local skills or AI code."""

from __future__ import annotations

import argparse
import tarfile
from datetime import datetime
from pathlib import Path


FILES = [
    "main.py",
    "run.py",
    "scheduler.py",
    "news_api.py",
    "config.py",
    "models.py",
    "requirements.txt",
    "market_calendar_overrides.json",
    "market_data",
    "spiders",
    "parsers",
    "storage",
    "filters",
    "utils",
    "deploy/stock-data.env.example",
    "deploy/systemd",
    "deploy/install.sh",
    "deploy/backup_data.sh",
    "SERVER_DEPLOYMENT.md",
    "SERVER_DATA_PIPELINE_OPTIMIZATION_CHECKLIST.md",
]


def excluded(path: Path) -> bool:
    if path.name == "news_enricher.py":
        return True
    if path.name == "market_scoring.py":
        return True
    return any(part in {"__pycache__", ".DS_Store"} for part in path.parts) or path.suffix in {".pyc", ".pyo"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the objective data server release bundle.")
    parser.add_argument("--output-dir", default="dist")
    parser.add_argument("--version", default=datetime.now().strftime("%Y%m%d-%H%M"))
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    package_name = f"stock-data-server-{args.version}"
    output_path = output_dir / f"{package_name}.tar.gz"

    with tarfile.open(output_path, "w:gz") as archive:
        for relative in FILES:
            source = root / relative
            if not source.exists():
                raise FileNotFoundError(source)
            if source.is_file():
                archive.add(source, arcname=f"{package_name}/{relative}")
                continue
            for path in source.rglob("*"):
                if path.is_file() and not excluded(path):
                    arcname = f"{package_name}/{path.relative_to(root)}"
                    archive.add(path, arcname=arcname)

    print(output_path)


if __name__ == "__main__":
    main()
