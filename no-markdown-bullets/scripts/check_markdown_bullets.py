#!/usr/bin/env python3
"""Report Markdown unordered-list markers without modifying the input."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, TextIO

__version__ = "0.2.0"

FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})(?:[^`]*)$")
UNORDERED_RE = re.compile(r"^([-+*])(?:[ \t]+|$)")
ORDERED_RE = re.compile(r"^\d{1,9}[.)](?:[ \t]+|$)")
QUOTE_RE = re.compile(r"^[ \t]{0,3}>[ \t]?")
IGNORED_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__"}

SUPPRESSION_OFF = "no-markdown-bullets: off"
SUPPRESSION_ON = "no-markdown-bullets: on"
SUPPRESSION_RE = re.compile(
    r"^<!--\s*no-markdown-bullets:\s*(off|on)\b(.*?)-->\s*$"
)
SUPPRESSION_REASON_RE = re.compile(r"""reason\s*=\s*("[^"]*"|'[^']*')""")

FRONTMATTER_FENCES = ("---", "+++")
FRONTMATTER_MAX_LINES = 200

CODE_UNORDERED = "unordered-list"
CODE_UNCLOSED = "unclosed-suppression"


@dataclass(frozen=True)
class Finding:
    line: int
    message: str
    code: str

    def format(self, source: str) -> str:
        return f"{source}:{self.line}: {self.message}"


@dataclass(frozen=True)
class Fence:
    character: str
    length: int


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    suppressed_lines: int = 0
    suppression_blocks: int = 0

    def as_dict(self) -> dict:
        return {
            "findings": [
                {"line": finding.line, "code": finding.code, "message": finding.message}
                for finding in self.findings
            ],
            "suppressed_lines": self.suppressed_lines,
            "suppression_blocks": self.suppression_blocks,
        }


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


def _frontmatter_end(lines: list[str]) -> int:
    """Return the 1-based last line of a closed frontmatter block, else 0.

    The check stays deliberately conservative: the opening line must be a bare
    ``---`` or ``+++``, the block may not contain a blank line, and a closing
    line of the same form must appear within ``FRONTMATTER_MAX_LINES``. Anything
    ambiguous is treated as ordinary Markdown so that body text is never
    swallowed.
    """
    if not lines:
        return 0
    opening = lines[0].rstrip()
    if opening not in FRONTMATTER_FENCES:
        return 0
    limit = min(len(lines), FRONTMATTER_MAX_LINES + 1)
    for index in range(1, limit):
        line = lines[index].rstrip()
        if not line:
            return 0
        if line == opening:
            return index + 1
    return 0


def _suppression_command(content: str) -> Optional[tuple[str, bool]]:
    """Return (action, has_reason) for a well-formed suppression comment."""
    match = SUPPRESSION_RE.match(content)
    if not match:
        return None
    action = match.group(1)
    reason = SUPPRESSION_REASON_RE.search(match.group(2) or "")
    has_reason = bool(reason and reason.group(1)[1:-1].strip())
    return action, has_reason


def scan_document(text: str) -> ScanResult:
    """Scan text and report unordered lists plus suppression bookkeeping."""
    lines = text.splitlines()
    result = ScanResult()
    skip_until = _frontmatter_end(lines)

    fences: dict[int, Fence] = {}
    list_indents: dict[int, list[int]] = {}
    suppression_start = 0

    for line_number, raw_line in enumerate(lines, start=1):
        if line_number <= skip_until:
            continue

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

        command = _suppression_command(content)
        if command:
            action, has_reason = command
            if action == "off" and has_reason and not suppression_start:
                suppression_start = line_number
                result.suppression_blocks += 1
            elif action == "on" and suppression_start:
                suppression_start = 0
            # Without a reason the directive is ignored; the region keeps being
            # checked, which surfaces the exception instead of hiding it.
            continue

        if suppression_start:
            result.suppressed_lines += 1
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
            result.findings.append(
                Finding(
                    line_number,
                    f"Markdown unordered list marker '{marker}'",
                    CODE_UNORDERED,
                )
            )
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

    if suppression_start:
        result.findings.append(
            Finding(
                suppression_start,
                "Unclosed suppression block, expected "
                f"'<!-- {SUPPRESSION_ON} reason=\"...\" -->'",
                CODE_UNCLOSED,
            )
        )

    return result


def scan_text(text: str) -> list[Finding]:
    """Return findings only, kept for callers that do not need statistics."""
    return scan_document(text).findings


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
    output_format: str = "text",
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    values = list(paths)
    if allow and len(values) > 1:
        print(
            "--allow accepts a single path; use inline suppression for "
            "per-file exceptions",
            file=stderr,
        )
        return 2

    failed = False
    total_findings = 0
    total_suppressed = 0
    records: list[dict] = []

    for value in values:
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
            result = scan_document(text)
            found = len(result.findings)
            total_findings += found
            total_suppressed += result.suppressed_lines
            if output_format == "json":
                records.append(
                    {"path": source, **result.as_dict()}
                )
            else:
                for finding in result.findings:
                    print(finding.format(source), file=stdout)

    if output_format == "json":
        payload = {
            "tool": "check_markdown_bullets",
            "version": __version__,
            "files": records,
            "summary": {
                "files": len(records),
                "findings": total_findings,
                "suppressed_lines": total_suppressed,
                "suppression_ratio": _ratio(total_suppressed, total_findings),
            },
        }
        json.dump(payload, stdout, ensure_ascii=False, indent=2)
        print("", file=stdout)

    if failed:
        return 2
    if total_findings and not allow:
        return 1
    return 0


def _ratio(suppressed: int, findings: int) -> float:
    total = suppressed + findings
    if not total:
        return 0.0
    return round(suppressed / total, 4)


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
        help="report findings but return success; single path only",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        dest="output_format",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    args = parser.parse_args(argv)
    return run(
        args.paths,
        allow=args.allow,
        output_format=args.output_format,
    )


if __name__ == "__main__":
    raise SystemExit(main())
