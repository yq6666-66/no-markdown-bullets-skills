#!/usr/bin/env python3
"""Report Markdown unordered-list markers without modifying the input."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, TextIO

FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})(?:[^`]*)$")
UNORDERED_RE = re.compile(r"^([-+*])(?:[ \t]+|$)")
ORDERED_RE = re.compile(r"^\d{1,9}[.)](?:[ \t]+|$)")
QUOTE_RE = re.compile(r"^[ \t]{0,3}>[ \t]?")
IGNORED_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__"}


@dataclass(frozen=True)
class Finding:
    line: int
    marker: str

    def format(self, source: str) -> str:
        return f"{source}:{self.line}: Markdown unordered list marker '{self.marker}'"


@dataclass(frozen=True)
class Fence:
    character: str
    length: int


def _container(line: str) -> tuple[int, str]:
    """Return blockquote depth and the content inside that container."""
    depth = 0
    rest = line
    while True:
        match = QUOTE_RE.match(rest)
        if not match:
            return depth, rest
        depth += 1
        rest = rest[match.end() :]


def _strip_quotes(line: str, limit: int) -> str:
    """Remove at most ``limit`` blockquote markers from a line."""
    rest = line
    for _ in range(limit):
        match = QUOTE_RE.match(rest)
        if not match:
            break
        rest = rest[match.end() :]
    return rest


def _indent_width(rest: str) -> int:
    prefix = rest[: len(rest) - len(rest.lstrip(" \t"))]
    return len(prefix.expandtabs(4))


def _is_thematic_break(rest: str, marker: str) -> bool:
    compact = rest.replace(" ", "").replace("\t", "")
    return len(compact) >= 3 and set(compact) == {marker}


def _opening_fence(rest: str, indent: int, has_active_list: bool) -> Optional[Fence]:
    if indent > 3 and not has_active_list:
        return None
    match = FENCE_RE.match(rest)
    if not match:
        return None
    token = match.group(1)
    return Fence(token[0], len(token))


def _is_closing_fence(rest: str, fence: Fence) -> bool:
    stripped = rest.strip(" \t")
    return (
        len(stripped) >= fence.length
        and set(stripped) == {fence.character}
    )


def scan_text(text: str) -> list[Finding]:
    """Find actual list syntax while ignoring code and thematic breaks.

    This intentionally implements only the Markdown structure needed for this
    check. It does not rewrite content or perform general Markdown linting.
    """
    findings: list[Finding] = []
    fences: dict[int, Fence] = {}
    list_indents: dict[int, list[int]] = {}

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        depth, rest = _container(raw_line)

        if fences:
            fence_depth = max(fences)
            fence = fences[fence_depth]
            if depth >= fence_depth:
                # Inside the fenced block. Content such as "> - item" is
                # literal code here, not a list.
                if _is_closing_fence(_strip_quotes(raw_line, fence_depth), fence):
                    for key in [key for key in fences if key >= fence_depth]:
                        del fences[key]
                continue
            # A shallower line ends the enclosing blockquote, and with it any
            # fence opened inside that blockquote.
            for key in [key for key in fences if key > depth]:
                del fences[key]

        indent = _indent_width(rest)
        content = rest.lstrip(" \t")
        active_lists = list_indents.setdefault(depth, [])
        opening = _opening_fence(rest, indent, bool(active_lists))
        if opening:
            fences[depth] = opening
            continue

        if not content:
            continue

        unordered = UNORDERED_RE.match(content)
        ordered = ORDERED_RE.match(content)

        if indent >= 4 and not active_lists:
            # At top level this is an indented code block, not a list.
            continue

        if unordered:
            marker = unordered.group(1)
            if _is_thematic_break(content, marker):
                active_lists.clear()
                continue
            findings.append(Finding(line_number, marker))
        elif not ordered:
            if active_lists and indent > active_lists[-1]:
                continue
            active_lists.clear()
            continue

        while active_lists and indent < active_lists[-1]:
            active_lists.pop()
        if active_lists and indent == active_lists[-1]:
            continue
        active_lists.append(indent)

    return findings


def _markdown_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    for candidate in sorted(path.rglob("*")):
        if not candidate.is_file() or candidate.suffix.lower() != ".md":
            continue
        if any(part in IGNORED_DIRS for part in candidate.parts):
            continue
        yield candidate


def _read(path: Path, stdin: TextIO) -> str:
    if str(path) == "-":
        return stdin.read()
    return path.read_text(encoding="utf-8-sig")


def run(
    paths: Iterable[str],
    *,
    allow: bool = False,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    found = False
    failed = False
    for value in paths:
        path = Path(value)
        if value != "-" and not path.exists():
            print(f"{value}: path does not exist", file=stderr)
            failed = True
            continue
        if value != "-" and not path.is_file() and not path.is_dir():
            print(f"{value}: unsupported input type", file=stderr)
            failed = True
            continue
        candidates = [path] if value == "-" else _markdown_files(path)
        for candidate in candidates:
            try:
                text = _read(candidate, stdin)
            except (OSError, UnicodeError) as error:
                print(f"{candidate}: {error}", file=stderr)
                failed = True
                continue
            source = "<stdin>" if value == "-" else str(candidate)
            for finding in scan_text(text):
                found = True
                print(finding.format(source), file=stdout)
    if failed:
        return 2
    if found and not allow:
        return 1
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report Markdown unordered lists; never modify the input."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Markdown files/directories to scan, or - for stdin (default: .)",
    )
    parser.add_argument(
        "--allow",
        action="store_true",
        help="report findings but return success for an explicit per-output override",
    )
    args = parser.parse_args(argv)
    return run(args.paths, allow=args.allow)


if __name__ == "__main__":
    raise SystemExit(main())
