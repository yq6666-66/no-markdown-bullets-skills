#!/usr/bin/env python3
"""Compare directory walking between two checker versions.

Builds a temporary tree that looks like a repository with a large ignored
directory, then times how long each implementation needs to enumerate the same
Markdown files. The file sets must match exactly, otherwise the script fails:
a faster walk that misses documents is not an optimisation.

Usage:
    python benchmarks/bench_walk.py --baseline /path/to/old/checker.py
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import tempfile
import time
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = (
    REPO_ROOT / "no-markdown-bullets" / "scripts" / "check_markdown_bullets.py"
)


def load_checker(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"walk_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_tree(root: Path, docs: int, noise: int) -> None:
    for index in range(docs):
        folder = root / f"docs{counter_band(index)}" / f"part{index % 40}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"note-{index}.md").write_text("1. fine\n", encoding="utf-8")
    for ignored in ("node_modules", ".venv", "__pycache__"):
        folder = root / ignored / "pkg"
        folder.mkdir(parents=True, exist_ok=True)
        for index in range(noise):
            (folder / f"file-{index}.md").write_text("- noise\n", encoding="utf-8")
    (root / "README.md").write_text("# root\n", encoding="utf-8")


def counter_band(index: int) -> int:
    return index % 25


def _walker(module: ModuleType):
    """Return the walker, tolerating the pre-0.2.1 private name."""
    for name in ("_iter_markdown_files", "_markdown_files"):
        walker = getattr(module, name, None)
        if walker is not None:
            return walker
    raise SystemExit(f"{module.__name__} exposes no Markdown walker")


def enumerate_files(module: ModuleType, root: Path) -> list[str]:
    return [str(path) for path in _walker(module)(root)]


def time_walk(module: ModuleType, root: Path, runs: int) -> float:
    enumerate_files(module, root)
    best = float("inf")
    for _ in range(runs):
        start = time.perf_counter()
        enumerate_files(module, root)
        best = min(best, time.perf_counter() - start)
    return best


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument("--docs", type=int, default=1200)
    parser.add_argument("--noise", type=int, default=1500)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        build_tree(root, args.docs, args.noise)
        total = sum(1 for _ in root.rglob("*.md"))
        print(f"tree: {args.docs} docs, {total - args.docs} ignored-side files")

        target = load_checker(args.target)
        target_files = enumerate_files(target, root)
        target_time = time_walk(target, root, args.runs)
        print(f"target:   {len(target_files):5d} files  {target_time * 1000:7.2f} ms")

        if args.baseline is None:
            return 0

        baseline = load_checker(args.baseline)
        baseline_files = enumerate_files(baseline, root)
        baseline_time = time_walk(baseline, root, args.runs)
        print(
            f"baseline: {len(baseline_files):5d} files  "
            f"{baseline_time * 1000:7.2f} ms"
        )

        if baseline_files != target_files:
            # Only two outcomes are acceptable: the target enumerates the same
            # set, or it skipped files that live under a directory the target
            # explicitly ignores. Anything else is a real regression.
            ignored = getattr(target, "IGNORED_DIRS", frozenset())
            extras = set(baseline_files) - set(target_files)
            omissions = set(target_files) - set(baseline_files)
            unjustified = [
                path
                for path in extras
                if not ignored.intersection(Path(path).parts)
            ]
            if omissions or unjustified:
                print("MISMATCH: file sets differ unexpectedly")
                print(f"  missing from target: {sorted(omissions)[:5]}")
                print(f"  excluded without ignore rule: {sorted(unjustified)[:5]}")
                return 1
            print(
                f"scope: {len(extras)} files now excluded by IGNORED_DIRS "
                f"({sorted(ignored)})"
            )

        delta = (target_time - baseline_time) / baseline_time * 100
        print(f"delta: {delta:+.2f}%  no unexpected file-set change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
