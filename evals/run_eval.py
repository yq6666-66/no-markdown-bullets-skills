#!/usr/bin/env python3
"""Measure whether the rule changes what a model actually writes.

scripts/strip_md_ul.py proves the stripper is correct. It says nothing about
whether the rule works. This harness closes that gap with a small, honest
measurement: eight fixed prompts, scored on structure, run under two
conditions that are then compared. Bullet counts are the stripper's
stripped_lines. Regions the stripper preserves, including front matter and
suppression, are not counted. CI validates the prompt set only; it does not
call a model.

What it can show: under condition B the share of answers containing unordered
lists is lower than under condition A, while ordered lists and tables survive,
and explanations stay prose instead of turning into numbered lists.

What it cannot show: why. Without both conditions there is no attribution, so a
single run is a baseline, not a result. The harness prints that reminder.

Two ways to feed it:

    # 1. Score outputs you already recorded
    python evals/run_eval.py --samples evals/samples --condition with-skill

    # 2. Generate with any command that reads a prompt on stdin
    python evals/run_eval.py --command "my-agent --print" --condition with-skill

Then compare the two result files:

    python evals/run_eval.py --compare results/a.json results/b.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import util as importlib_util
from pathlib import Path
from types import ModuleType
from typing import TextIO

__version__ = "0.1.0"

REPO_ROOT = Path(__file__).resolve().parents[1]
STRIPPER_PATH = REPO_ROOT / "scripts" / "strip_md_ul.py"
PROMPTS_PATH = Path(__file__).resolve().parent / "prompts.json"

ORDERED_RE = re.compile(r"^[ \t]*\d{1,9}[.)][ \t]+")
FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
TABLE_SEPARATOR_RE = re.compile(r"^[ \t]*\|?[ \t:|-]*-[ \t:|-]*$")
STRUCTURAL_PREFIXES = ("#", "|", ">")

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

KNOWN_EXPECTATIONS = frozenset(
    {"prose", "ordered", "table", "table_or_ordered", "ordered_or_prose"}
)


@dataclass(frozen=True)
class Prompt:
    """One fixed request plus the structure the rule prefers for it."""

    id: str
    text: str
    expect: str
    note: str


@dataclass(frozen=True)
class Analysis:
    """Structure counts for one answer."""

    bullets: int
    ordered: int
    tables: int
    paragraphs: int
    chars: int
    longest_block: int

    def meets(self, expect: str) -> bool:
        if expect == "prose":
            return self.bullets == 0 and self.ordered == 0
        if expect == "ordered":
            return self.ordered >= 2
        if expect == "table":
            return self.tables >= 1
        if expect == "table_or_ordered":
            return self.tables >= 1 or self.ordered >= 2
        if expect == "ordered_or_prose":
            return self.ordered >= 2 or (self.bullets == 0 and self.paragraphs >= 1)
        raise ValueError(f"unknown expectation: {expect}")


@dataclass(frozen=True)
class Row:
    """Per-prompt score."""

    id: str
    expect: str
    bullets: int
    ordered: int
    tables: int
    paragraphs: int
    chars: int
    longest_block: int
    expectation_met: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "expect": self.expect,
            "bullets": self.bullets,
            "ordered": self.ordered,
            "tables": self.tables,
            "paragraphs": self.paragraphs,
            "chars": self.chars,
            "longest_block": self.longest_block,
            "expectation_met": self.expectation_met,
        }


@dataclass(frozen=True)
class RunResult:
    """One scored condition."""

    condition: str
    rows: list[Row]
    stripper_version: str
    generated_at: str

    def summary(self) -> dict[str, object]:
        outputs = len(self.rows)
        if not outputs:
            return {
                "outputs": 0,
                "bullet_outputs": 0,
                "bullet_rate": 0.0,
                "ordered_outputs": 0,
                "table_outputs": 0,
                "expectation_met": 0,
                "expectation_rate": 0.0,
                "mean_chars": 0,
                "mean_longest_block": 0,
            }
        bullet_outputs = sum(1 for row in self.rows if row.bullets > 0)
        met = sum(1 for row in self.rows if row.expectation_met)
        return {
            "outputs": outputs,
            "bullet_outputs": bullet_outputs,
            "bullet_rate": round(bullet_outputs / outputs, 4),
            "ordered_outputs": sum(1 for row in self.rows if row.ordered > 0),
            "table_outputs": sum(1 for row in self.rows if row.tables > 0),
            "expectation_met": met,
            "expectation_rate": round(met / outputs, 4),
            "mean_chars": round(sum(row.chars for row in self.rows) / outputs),
            "mean_longest_block": round(
                sum(row.longest_block for row in self.rows) / outputs
            ),
        }

    def bullet_rate(self) -> float:
        """Share of answers that contain at least one unordered list."""
        if not self.rows:
            return 0.0
        hit = sum(1 for row in self.rows if row.bullets > 0)
        return round(hit / len(self.rows), 4)

    def as_dict(self) -> dict[str, object]:
        return {
            "tool": "run_eval",
            "version": __version__,
            "condition": self.condition,
            "stripper_version": self.stripper_version,
            "generated_at": self.generated_at,
            "prompts": [row.as_dict() for row in self.rows],
            "summary": self.summary(),
        }


def load_stripper() -> ModuleType:
    spec = importlib_util.spec_from_file_location("eval_stripper", STRIPPER_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import {STRIPPER_PATH}")
    module = importlib_util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _blocks(text: str) -> list[list[str]]:
    """Split into blank-line separated blocks, keeping fenced code intact."""
    blocks: list[list[str]] = []
    current: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        match = FENCE_RE.match(line)
        if fence is None and match:
            fence = match.group(1)[0]
        elif fence is not None and match and match.group(1)[0] == fence:
            fence = None
        if not line.strip():
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _is_table(block: Sequence[str]) -> bool:
    if len(block) < 2 or "|" not in block[0]:
        return False
    return bool(TABLE_SEPARATOR_RE.match(block[1])) and "-" in block[1]


def _is_list(block: Sequence[str]) -> bool:
    if ORDERED_RE.match(block[0]):
        return True
    head = block[0].lstrip()
    return head[:1] in ("-", "*", "+") and len(head) > 1 and head[1] in " \t"


def analyse(text: str, stripper: ModuleType) -> Analysis:
    """Count structure. Bullets are the stripper's stripped lines; the rewrite is discarded."""
    bullets = len(stripper.strip_text(text).stripped_lines)

    ordered = 0
    fence: str | None = None
    for line in text.splitlines():
        match = FENCE_RE.match(line)
        if fence is None and match:
            fence = match.group(1)[0]
            continue
        if fence is not None:
            if match and match.group(1)[0] == fence:
                fence = None
            continue
        if ORDERED_RE.match(line):
            ordered += 1

    tables = 0
    paragraphs = 0
    longest = 0
    for block in _blocks(text):
        head = block[0].lstrip()
        if _is_table(block):
            tables += 1
            continue
        if _is_list(block):
            continue
        if head.startswith(STRUCTURAL_PREFIXES) or head.startswith("```"):
            continue
        paragraphs += 1
        longest = max(longest, len(" ".join(block)))

    return Analysis(
        bullets=bullets,
        ordered=ordered,
        tables=tables,
        paragraphs=paragraphs,
        chars=len(text),
        longest_block=longest,
    )


def _require_mapping(value: object, where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SystemExit(f"{where}: expected a JSON object")
    return value


def _require_string(container: dict[str, object], key: str, where: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"{where}: '{key}' must be a non-empty string")
    return value


def load_prompts(path: Path) -> list[Prompt]:
    document = _require_mapping(json.loads(path.read_text(encoding="utf-8")), str(path))
    items = document.get("prompts")
    if not isinstance(items, list) or not items:
        raise SystemExit(f"{path}: 'prompts' must be a non-empty list")
    prompts: list[Prompt] = []
    seen: set[str] = set()
    for item in items:
        entry = _require_mapping(item, str(path))
        prompt_id = _require_string(entry, "id", str(path))
        if prompt_id in seen:
            raise SystemExit(f"{path}: duplicate id '{prompt_id}'")
        seen.add(prompt_id)
        prompts.append(
            Prompt(
                id=prompt_id,
                text=_require_string(entry, "text", str(path)),
                expect=_require_string(entry, "expect", str(path)),
                note=str(entry.get("note", "")),
            )
        )
    return prompts


def _read_samples(root: Path, condition: str, prompt_id: str) -> str | None:
    for candidate in (root / condition / f"{prompt_id}.md", root / f"{prompt_id}.md"):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return None


def _run_command(command: str, prompt: str, timeout: int) -> str:
    completed = subprocess.run(
        command,
        input=prompt,
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"command failed with exit code {completed.returncode}: "
            f"{completed.stderr.strip()[:400]}"
        )
    return completed.stdout


def collect(
    prompts: Sequence[Prompt],
    *,
    samples: Path | None,
    condition: str,
    command: str | None,
    timeout: int,
    stderr: TextIO,
) -> list[tuple[Prompt, str]]:
    outputs: list[tuple[Prompt, str]] = []
    for prompt in prompts:
        if command:
            text = _run_command(command, prompt.text, timeout)
        elif samples is not None:
            found = _read_samples(samples, condition, prompt.id)
            if found is None:
                print(
                    f"warning: no sample for '{prompt.id}' under {samples}",
                    file=stderr,
                )
                continue
            text = found
        else:
            raise SystemExit("either --samples or --command is required")
        outputs.append((prompt, text))
    return outputs


def evaluate(
    outputs: Sequence[tuple[Prompt, str]], stripper: ModuleType
) -> list[Row]:
    rows: list[Row] = []
    for prompt, text in outputs:
        analysis = analyse(text, stripper)
        rows.append(
            Row(
                id=prompt.id,
                expect=prompt.expect,
                bullets=analysis.bullets,
                ordered=analysis.ordered,
                tables=analysis.tables,
                paragraphs=analysis.paragraphs,
                chars=analysis.chars,
                longest_block=analysis.longest_block,
                expectation_met=analysis.meets(prompt.expect),
            )
        )
    return rows


def _print_table(result: RunResult, stdout: TextIO) -> None:
    print("| prompt | expect | bullets | ordered | tables | paras | met |", file=stdout)
    print("| --- | --- | --- | --- | --- | --- | --- |", file=stdout)
    for row in result.rows:
        met = "yes" if row.expectation_met else "no"
        print(
            f"| {row.id} | {row.expect} | {row.bullets} | {row.ordered} | "
            f"{row.tables} | {row.paragraphs} | {met} |",
            file=stdout,
        )
    summary = result.summary()
    print("", file=stdout)
    print(
        f"condition: {result.condition}  outputs: {summary['outputs']}  "
        f"bullet_rate: {summary['bullet_rate']}  "
        f"expectation_rate: {summary['expectation_rate']}",
        file=stdout,
    )


def _row_from_dict(entry: dict[str, object], where: str) -> Row:
    def number(key: str) -> int:
        value = entry.get(key, 0)
        if not isinstance(value, int):
            raise SystemExit(f"{where}: '{key}' must be an integer")
        return value

    met = entry.get("expectation_met", False)
    return Row(
        id=_require_string(entry, "id", where),
        expect=str(entry.get("expect", "")),
        bullets=number("bullets"),
        ordered=number("ordered"),
        tables=number("tables"),
        paragraphs=number("paragraphs"),
        chars=number("chars"),
        longest_block=number("longest_block"),
        expectation_met=bool(met),
    )


def load_result(path: Path) -> RunResult:
    """Read a result file written by this tool."""
    document = _require_mapping(json.loads(path.read_text(encoding="utf-8")), str(path))
    items = document.get("prompts")
    if not isinstance(items, list):
        raise SystemExit(f"{path}: 'prompts' must be a list")
    rows = [
        _row_from_dict(_require_mapping(item, str(path)), str(path)) for item in items
    ]
    return RunResult(
        condition=str(document.get("condition", path.stem)),
        rows=rows,
        stripper_version=str(
            document.get("stripper_version", document.get("checker_version", "unknown"))
        ),
        generated_at=str(document.get("generated_at", "")),
    )


def compare(first_path: Path, second_path: Path, stdout: TextIO) -> int:
    first = load_result(first_path)
    second = load_result(second_path)
    label_a, label_b = first.condition, second.condition

    index_a = {row.id: row for row in first.rows}
    index_b = {row.id: row for row in second.rows}

    print(
        f"| prompt | bullets {label_a} | bullets {label_b} | "
        f"met {label_a} | met {label_b} |",
        file=stdout,
    )
    print("| --- | --- | --- | --- | --- |", file=stdout)
    for prompt_id in sorted(set(index_a) | set(index_b)):
        row_a = index_a.get(prompt_id)
        row_b = index_b.get(prompt_id)
        bullets_a = row_a.bullets if row_a else "-"
        bullets_b = row_b.bullets if row_b else "-"
        met_a = "yes" if row_a and row_a.expectation_met else "no"
        met_b = "yes" if row_b and row_b.expectation_met else "no"
        print(
            f"| {prompt_id} | {bullets_a} | {bullets_b} | {met_a} | {met_b} |",
            file=stdout,
        )

    print("", file=stdout)
    for label, result in ((label_a, first), (label_b, second)):
        summary = result.summary()
        print(
            f"{label}: bullet_rate={summary['bullet_rate']} "
            f"expectation_rate={summary['expectation_rate']} "
            f"mean_chars={summary['mean_chars']}",
            file=stdout,
        )

    rate_a = first.bullet_rate()
    rate_b = second.bullet_rate()
    print("", file=stdout)
    print(
        f"bullet_rate delta ({label_b} - {label_a}): {rate_b - rate_a:+}",
        file=stdout,
    )
    print(
        "A negative delta is the intended direction. It does not by itself "
        "prove the rule caused it: check that both runs used the same model, "
        "temperature and prompt text.",
        file=stdout,
    )
    return EXIT_OK


def run(
    *,
    samples: Path | None,
    condition: str,
    command: str | None,
    timeout: int,
    out: Path | None,
    prompts_path: Path,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    prompts = load_prompts(prompts_path)
    stripper = load_stripper()
    outputs = collect(
        prompts,
        samples=samples,
        condition=condition,
        command=command,
        timeout=timeout,
        stderr=stderr,
    )
    result = RunResult(
        condition=condition,
        rows=evaluate(outputs, stripper),
        stripper_version=str(getattr(stripper, "__version__", "unknown")),
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    _print_table(result, stdout)

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(result.as_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("", file=stdout)
        print(f"wrote {out}", file=stdout)

    print("", file=stdout)
    print(
        "This is one condition, not a result. Run a control condition and "
        "compare before claiming the rule had an effect.",
        file=stdout,
    )
    return EXIT_OK if outputs else EXIT_ERROR


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_eval",
        description="Measure unordered-list emission across fixed prompts.",
    )
    parser.add_argument(
        "--samples", type=Path, default=None, help="directory of recorded answers"
    )
    parser.add_argument(
        "--command",
        default=None,
        help="command that reads a prompt on stdin and writes an answer",
    )
    parser.add_argument(
        "--condition",
        default="default",
        help="label for this run, e.g. baseline or with-skill",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="per-answer timeout in seconds (default: 180)",
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="write the JSON result here"
    )
    parser.add_argument(
        "--prompts", type=Path, default=PROMPTS_PATH, help="prompt set to use"
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        type=Path,
        metavar=("A", "B"),
        help="compare two result files instead of running",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="list the prompts and exit"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    args = parser.parse_args(argv)

    if args.compare:
        return compare(args.compare[0], args.compare[1], sys.stdout)

    if args.dry_run:
        for prompt in load_prompts(args.prompts):
            print(f"{prompt.id:22s} expect={prompt.expect}")
        return EXIT_OK

    if not args.samples and not args.command:
        parser.error("either --samples or --command is required")

    return run(
        samples=args.samples,
        condition=args.condition,
        command=args.command,
        timeout=args.timeout,
        out=args.out,
        prompts_path=args.prompts,
    )


if __name__ == "__main__":
    raise SystemExit(main())
