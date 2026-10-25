#!/usr/bin/env python3
"""Report Markdown unordered-list markers without modifying the input.

The checker is deliberately small. It makes a single pass over each document,
keeps no state between files, and never writes to what it scans.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, NamedTuple, Optional, Sequence, TextIO

__all__ = [
    "Finding",
    "ScanResult",
    "scan_document",
    "scan_text",
    "run",
    "main",
    "EXIT_OK",
    "EXIT_FINDINGS",
    "EXIT_ERROR",
    "__version__",
]

__version__ = "0.2.1"

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})(?:[^`]*)$")
UNORDERED_RE = re.compile(r"^([-+*])(?:[ \t]+|$)")
ORDERED_RE = re.compile(r"^\d{1,9}[.)](?:[ \t]+|$)")
QUOTE_RE = re.compile(r"^[ \t]{0,3}>[ \t]?")
IGNORED_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__"}

SUPPRESSION_OFF = "no-markdown-bullets: off"
SUPPRESSION_ON = "no-markdown-bullets: on"
SUPPRESSION_RE = re.compile(r"^<!--\s*no-markdown-bullets:\s*(off|on)\b(.*?)-->\s*$")
SUPPRESSION_REASON_RE = re.compile(r"""reason\s*=\s*("[^"]*"|'[^']*')""")

FRONTMATTER_MARKERS = ("---", "+++")
FRONTMATTER_MAX_LINES = 200

CODE_UNORDERED = "unordered-list"
CODE_UNCLOSED = "unclosed-suppression"

FILENAME_SUFFIX = ".md"


@dataclass(frozen=True)
class Finding:
    """One reported problem, positioned by line number."""

    line: int
    message: str
    code: str

    def format(self, source: str) -> str:
        return f"{source}:{self.line}: {self.message}"


@dataclass(frozen=True)
class Fence:
    """An open fenced code block, tracked per blockquote depth."""

    character: str
    length: int


@dataclass
class ScanResult:
    """Findings plus the bookkeeping needed to audit exceptions."""

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


class _Directive(NamedTuple):
    """A parsed suppression comment."""

    action: str
    has_reason: bool


@dataclass
class _Totals:
    """Aggregate counters for one CLI run."""

    files: int = 0
    findings: int = 0
    suppressed: int = 0

    def ratio(self) -> float:
        total = self.suppressed + self.findings
        return round(self.suppressed / total, 4) if total else 0.0


def _split_quote_prefix(line: str, limit: Optional[int] = None) -> tuple[int, str]:
    """Strip up to ``limit`` blockquote markers and return (depth, remainder)."""
    depth = 0
    rest = line
    while limit is None or depth < limit:
        match = QUOTE_RE.match(rest)
        if not match:
            break
        depth += 1
        rest = rest[match.end() :]
    return depth, rest


def _indent_width(rest: str) -> int:
    """Return the visual width of leading whitespace, expanding tabs to 4."""
    width = 0
    for char in rest:
        if char == " ":
            width += 1
        elif char == "\t":
            width += 4 - (width % 4)
        else:
            break
    return width


def _is_thematic_break(content: str, marker: str) -> bool:
    """True for ``---``/``***`` style rules, which are not lists."""
    count = 0
    for char in content:
        if char == marker:
            count += 1
        elif char not in " \t":
            return False
    return count >= 3


def _opening_fence(rest: str, indent: int, has_active_list: bool) -> Optional[Fence]:
    """Return a fence if this line opens a fenced code block."""
    if indent > 3 and not has_active_list:
        return None
    match = FENCE_RE.match(rest)
    if not match:
        return None
    token = match.group(1)
    return Fence(token[0], len(token))


def _is_closing_fence(rest: str, fence: Fence) -> bool:
    """True if this line closes ``fence``: same character, at least as long."""
    stripped = rest.strip(" \t")
    return len(stripped) >= fence.length and set(stripped) == {fence.character}


def _frontmatter_last_line(lines: Sequence[str]) -> int:
    """Return the 1-based last line of a closed frontmatter block, else 0.

    The detection stays deliberately conservative: the opening line must be a
    bare ``---`` or ``+++``, the block may not contain a blank line, and a
    closing line of the same form must appear within ``FRONTMATTER_MAX_LINES``.
    Anything ambiguous is treated as ordinary Markdown so that body text is
    never swallowed.
    """
    if not lines:
        return 0
    opening = lines[0].rstrip()
    if opening not in FRONTMATTER_MARKERS:
        return 0
    limit = min(len(lines), FRONTMATTER_MAX_LINES + 1)
    for index in range(1, limit):
        line = lines[index].rstrip()
        if not line:
            return 0
        if line == opening:
            return index + 1
    return 0


def _parse_suppression_directive(content: str) -> Optional[_Directive]:
    """Parse a suppression comment, ignoring anything malformed."""
    match = SUPPRESSION_RE.match(content)
    if not match:
        return None
    reason = SUPPRESSION_REASON_RE.search(match.group(2) or "")
    has_reason = bool(reason and reason.group(1)[1:-1].strip())
    return _Directive(match.group(1), has_reason)


class _BlockScanner:
    """Line-oriented state machine for a single document.

    The scanner owns the only mutable state in the checker: open fences, the
    indentation stack per blockquote depth, and the active suppression range.
    Keeping it in an object makes the per-line steps individually readable and
    keeps ``scan_document`` a one-liner.
    """

    def __init__(self) -> None:
        self.result = ScanResult()
        self._fences: dict[int, Fence] = {}
        self._list_indents: dict[int, list[int]] = {}
        self._suppression_line: Optional[int] = None

    def scan(self, text: str) -> ScanResult:
        lines = text.splitlines()
        start = _frontmatter_last_line(lines) + 1
        for number in range(start, len(lines) + 1):
            self._feed(number, lines[number - 1])
        self._report_unclosed_suppression()
        return self.result

    def _feed(self, number: int, raw_line: str) -> None:
        depth, rest = _split_quote_prefix(raw_line)

        if self._fences and self._consume_fenced(raw_line, depth):
            return

        indent = _indent_width(rest)
        content = rest.lstrip(" \t")
        active_lists = self._list_indents.setdefault(depth, [])

        opening = _opening_fence(rest, indent, bool(active_lists))
        if opening:
            self._fences[depth] = opening
            return

        if not content:
            return

        if self._handle_suppression(content, number):
            return

        if self._suppression_line is not None:
            self.result.suppressed_lines += 1
            return

        if indent >= 4 and not active_lists:
            # At top level this is an indented code block, not a list.
            return

        unordered = UNORDERED_RE.match(content)
        ordered = ORDERED_RE.match(content)

        if unordered:
            marker = unordered.group(1)
            if _is_thematic_break(content, marker):
                active_lists.clear()
                return
            self.result.findings.append(
                Finding(
                    number,
                    f"Markdown unordered list marker '{marker}'",
                    CODE_UNORDERED,
                )
            )
        elif not ordered:
            if active_lists and indent > active_lists[-1]:
                return
            active_lists.clear()
            return

        while active_lists and indent < active_lists[-1]:
            active_lists.pop()
        if active_lists and indent == active_lists[-1]:
            return
        active_lists.append(indent)

    def _consume_fenced(self, raw_line: str, depth: int) -> bool:
        """Advance through an open fence; True means the line was consumed."""
        fence_depth = max(self._fences)
        fence = self._fences[fence_depth]

        if depth >= fence_depth:
            # Content such as "> - item" inside a fence is literal code, not a
            # list, so the line never reaches the block parser.
            remainder = _split_quote_prefix(raw_line, fence_depth)[1]
            if _is_closing_fence(remainder, fence):
                for key in [key for key in self._fences if key >= fence_depth]:
                    del self._fences[key]
            return True

        # A shallower line ends the enclosing blockquote, and with it any fence
        # opened inside that blockquote.
        for key in [key for key in self._fences if key > depth]:
            del self._fences[key]
        return False

    def _handle_suppression(self, content: str, number: int) -> bool:
        """Apply a suppression directive; True means this line was a directive."""
        directive = _parse_suppression_directive(content)
        if directive is None:
            return False

        if directive.action == "off" and directive.has_reason:
            if self._suppression_line is None:
                self._suppression_line = number
                self.result.suppression_blocks += 1
        elif directive.action == "on":
            if self._suppression_line is not None:
                self._suppression_line = None
        # A directive without a reason is ignored on purpose: the region keeps
        # being checked, which surfaces the exception instead of hiding it.
        return True

    def _report_unclosed_suppression(self) -> None:
        if self._suppression_line is None:
            return
        self.result.findings.append(
            Finding(
                self._suppression_line,
                "Unclosed suppression block, expected "
                f'\'<!-- {SUPPRESSION_ON} reason="..." -->\'',
                CODE_UNCLOSED,
            )
        )
        self._suppression_line = None


def scan_document(text: str) -> ScanResult:
    """Scan a Markdown document and return findings plus suppression stats."""
    return _BlockScanner().scan(text)


def scan_text(text: str) -> list[Finding]:
    """Return findings only, kept for callers that do not need statistics."""
    return scan_document(text).findings


def _iter_markdown_files(path: Path) -> Iterable[Path]:
    """Yield the Markdown files under ``path`` in a stable order."""
    if path.is_file():
        yield path
        return
    for candidate in sorted(path.rglob("*")):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() != FILENAME_SUFFIX:
            continue
        if any(part in IGNORED_DIRS for part in candidate.parts):
            continue
        yield candidate


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _report_problem(stderr: TextIO, problems: list[str], message: str) -> None:
    """Record and immediately surface an input problem."""
    problems.append(message)
    print(message, file=stderr)


def _iter_documents(
    value: str,
    *,
    stdin: TextIO,
    stderr: TextIO,
    problems: list[str],
) -> Iterator[tuple[str, str]]:
    """Yield (source label, text) pairs for one CLI path argument."""
    if value == "-":
        yield "<stdin>", stdin.read()
        return

    path = Path(value)
    if not path.exists():
        _report_problem(stderr, problems, f"{value}: path does not exist")
        return
    if not path.is_file() and not path.is_dir():
        _report_problem(stderr, problems, f"{value}: unsupported input type")
        return

    candidates = (path,) if path.is_file() else _iter_markdown_files(path)
    for candidate in candidates:
        try:
            text = _read_text(candidate)
        except (OSError, UnicodeError) as error:
            _report_problem(stderr, problems, f"{candidate}: {error}")
            continue
        yield str(candidate), text


def _write_findings(stdout: TextIO, source: str, result: ScanResult) -> None:
    for finding in result.findings:
        print(finding.format(source), file=stdout)


def _write_json(
    stdout: TextIO, records: Sequence[dict], totals: _Totals
) -> None:
    payload = {
        "tool": "check_markdown_bullets",
        "version": __version__,
        "files": list(records),
        "summary": {
            "files": totals.files,
            "findings": totals.findings,
            "suppressed_lines": totals.suppressed,
            "suppression_ratio": totals.ratio(),
        },
    }
    json.dump(payload, stdout, ensure_ascii=False, indent=2)
    stdout.write("\n")


def run(
    paths: Iterable[str],
    *,
    allow: bool = False,
    output_format: str = "text",
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Scan every path and return the process exit code."""
    values = list(paths)
    if allow and len(values) > 1:
        print(
            "--allow accepts a single path; use inline suppression for "
            "per-file exceptions",
            file=stderr,
        )
        return EXIT_ERROR

    problems: list[str] = []
    records: list[dict] = []
    totals = _Totals()

    for value in values:
        for source, text in _iter_documents(
            value, stdin=stdin, stderr=stderr, problems=problems
        ):
            result = scan_document(text)
            totals.files += 1
            totals.findings += len(result.findings)
            totals.suppressed += result.suppressed_lines
            if output_format == "json":
                records.append({"path": source, **result.as_dict()})
            else:
                _write_findings(stdout, source, result)

    if output_format == "json":
        _write_json(stdout, records, totals)

    if problems:
        return EXIT_ERROR
    if totals.findings and not allow:
        return EXIT_FINDINGS
    return EXIT_OK


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_markdown_bullets",
        description="Report Markdown unordered lists; never modify the input.",
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
