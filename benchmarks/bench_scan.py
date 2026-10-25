#!/usr/bin/env python3
"""Measure scan throughput so refactors can be judged by numbers, not vibes.

Usage:
    python benchmarks/bench_scan.py
    python benchmarks/bench_scan.py --baseline /path/to/old/checker.py

The generated document mixes paragraphs, ordered lists, tables, fenced code
and blockquotes so the timing reflects realistic parser work rather than a
single hot branch.

Two details make the comparison trustworthy. A warmup pass is discarded, and
when a baseline is supplied the two implementations are timed in interleaved
ABBA order. Without interleaving the first implementation measured benefits
from a cold CPU: identical code showed a reproducible 11% "regression".
"""

from __future__ import annotations

import argparse
import importlib.util
import statistics
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = REPO_ROOT / "no-markdown-bullets" / "scripts" / "check_markdown_bullets.py"

SECTION = """## Section {index}

Paragraph text that describes the section in ordinary prose, long enough to
exercise the common path where a line is neither a list nor a fence.

1. First ordered step.
2. Second ordered step with `inline code`.
3. Third ordered step.

| Field | Meaning |
| --- | --- |
| alpha | first |
| beta | second |

> A quoted remark that spans a single line.

```python
def sample(value):
    return value * 2
```

---
"""


def load_checker(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"bench_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_document(sections: int) -> str:
    return "\n".join(SECTION.format(index=index) for index in range(sections))


def _time_once(scan: Callable[[str], object], text: str) -> float:
    start = time.perf_counter()
    scan(text)
    return time.perf_counter() - start


def measure(scan: Callable[[str], object], text: str, runs: int) -> float:
    """Return best seconds over ``runs`` passes after one discarded warmup."""
    scan(text)
    return min(_time_once(scan, text) for _ in range(runs))


def measure_pair(
    first: Callable[[str], object],
    second: Callable[[str], object],
    text: str,
    rounds: int,
) -> tuple[list[float], list[float]]:
    """Time two callables in ABBA order to cancel CPU warmup and drift."""
    first(text)
    second(text)
    first_times: list[float] = []
    second_times: list[float] = []
    for index in range(rounds):
        if index % 2 == 0:
            first_times.append(_time_once(first, text))
            second_times.append(_time_once(second, text))
        else:
            second_times.append(_time_once(second, text))
            first_times.append(_time_once(first, text))
    return first_times, second_times


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument("--sections", type=int, default=4000)
    parser.add_argument("--rounds", type=int, default=15)
    args = parser.parse_args(argv)

    text = build_document(args.sections)
    size_mb = len(text.encode("utf-8")) / (1024 * 1024)
    print(f"document: {args.sections} sections, {size_mb * 1024:.0f} KiB, {args.rounds} rounds")

    target = load_checker(args.target)
    if args.baseline is None:
        best = measure(target.scan_document, text, args.rounds)
        print(f"target: {best * 1000:8.2f} ms  {size_mb / best:7.2f} MB/s")
        return 0

    baseline = load_checker(args.baseline)
    base_times, target_times = measure_pair(
        baseline.scan_document, target.scan_document, text, args.rounds
    )
    base_best = min(base_times)
    target_best = min(target_times)
    base_median = statistics.median(base_times)
    target_median = statistics.median(target_times)

    print(f"baseline: {base_best * 1000:8.2f} ms best  {base_median * 1000:8.2f} ms median")
    print(f"target:   {target_best * 1000:8.2f} ms best  {target_median * 1000:8.2f} ms median")
    print(f"throughput: {size_mb / base_best:7.2f} -> {size_mb / target_best:7.2f} MB/s")
    delta_best = (target_best - base_best) / base_best * 100
    delta_median = (target_median - base_median) / base_median * 100
    print(f"delta: {delta_best:+.2f}% (best)  {delta_median:+.2f}% (median)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
