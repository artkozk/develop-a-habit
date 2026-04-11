#!/usr/bin/env python3
"""Fail CI if append-only docs have deletions."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

APPEND_ONLY_DOCS = [
    Path("docs/PRODUCT_SPEC_APPEND_ONLY.md"),
    Path("docs/AI_FUNCTIONAL_SPEC_APPEND_ONLY.md"),
    Path("docs/COMMITS_LOG.md"),
]


def run_git_diff(base_ref: str, target: Path) -> str:
    command = ["git", "diff", "--unified=0", base_ref, "--", str(target)]
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    if proc.returncode not in {0, 1}:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout


def has_deletions(diff_text: str) -> bool:
    for line in diff_text.splitlines():
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Check append-only docs")
    parser.add_argument("--base", default="origin/main", help="Git base ref for diff")
    args = parser.parse_args()

    failed: list[str] = []
    for doc in APPEND_ONLY_DOCS:
        if not doc.exists():
            failed.append(f"Missing append-only doc: {doc}")
            continue

        diff_text = run_git_diff(args.base, doc)
        if has_deletions(diff_text):
            failed.append(f"Append-only violation in {doc}")

    if failed:
        print("Append-only checks failed:")
        for item in failed:
            print(f"- {item}")
        return 1

    print("Append-only docs check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
