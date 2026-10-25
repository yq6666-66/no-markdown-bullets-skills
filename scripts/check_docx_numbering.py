#!/usr/bin/env python3
"""Report Word paragraphs that carry bullet numbering.

Markdown unordered lists are only one of three delivery surfaces. A Word file
reaches readers through ``numPr`` numbering definitions instead, so checking the
``.docx`` itself is the only way to confirm the Word scenario end to end.

The script reads the OOXML package directly with the standard library. It
reports paragraphs whose resolved number format is ``bullet``, resolving
numbering that comes from a paragraph style and its ``basedOn`` chain, not just
from a direct ``w:numPr``.

Usage:
    python scripts/check_docx_numbering.py report.docx
    python scripts/check_docx_numbering.py docs/*.docx --format json

Exit codes differ from scripts/strip_md_ul.py: 0 clean, 1 bullets found,
2 unreadable input. This tool only reports. It does not rewrite the file.
python-docx is not required to run it.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO
from xml.etree import ElementTree

__all__ = [
    "DocxResult",
    "ParagraphFinding",
    "scan_docx",
    "run",
    "main",
    "EXIT_OK",
    "EXIT_FINDINGS",
    "EXIT_ERROR",
]

__version__ = "0.1.0"

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

WORDML = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

DOCUMENT_PART = "word/document.xml"
NUMBERING_PART = "word/numbering.xml"
STYLES_PART = "word/styles.xml"

BULLET_FORMAT = "bullet"
SNIPPET_LIMIT = 48
STYLE_CHAIN_LIMIT = 12


def _qualified(tag: str) -> str:
    return f"{{{WORDML}}}{tag}"


W_P = _qualified("p")
W_PPR = _qualified("pPr")
W_NUMPR = _qualified("numPr")
W_ILVL = _qualified("ilvl")
W_NUMID = _qualified("numId")
W_PSTYLE = _qualified("pStyle")
W_T = _qualified("t")
W_STYLE = _qualified("style")
W_STYLE_ID = _qualified("styleId")
W_BASED_ON = _qualified("basedOn")
W_ABSTRACT_NUM = _qualified("abstractNum")
W_ABSTRACT_NUM_ID = _qualified("abstractNumId")
W_NUM = _qualified("num")
W_LVL = _qualified("lvl")
W_NUM_FMT = _qualified("numFmt")
W_VAL = _qualified("val")


@dataclass(frozen=True)
class ParagraphFinding:
    """A paragraph that resolves to bullet numbering."""

    index: int
    num_id: str
    level: str
    source: str
    text: str

    def format(self, path: str) -> str:
        where = f"numId={self.num_id}, level={self.level}, via {self.source}"
        snippet = self.text or "<empty>"
        return f"{path}: paragraph {self.index}: bullet numbering ({where}): {snippet}"


@dataclass
class DocxResult:
    """Findings plus the counts that make a ratio meaningful."""

    findings: list[ParagraphFinding] = field(default_factory=list)
    paragraphs: int = 0
    numbered: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "findings": [
                {
                    "paragraph": finding.index,
                    "num_id": finding.num_id,
                    "level": finding.level,
                    "source": finding.source,
                    "text": finding.text,
                }
                for finding in self.findings
            ],
            "paragraphs": self.paragraphs,
            "numbered": self.numbered,
        }


def _value(element: ElementTree.Element | None, name: str) -> str:
    if element is None:
        return ""
    return element.get(_qualified(name), "")


def _child(parent: ElementTree.Element, name: str) -> ElementTree.Element | None:
    return parent.find(_qualified(name))


def _grandchild(
    parent: ElementTree.Element, child_name: str, grandchild_name: str
) -> ElementTree.Element | None:
    child = _child(parent, child_name)
    if child is None:
        return None
    return _child(child, grandchild_name)


def _read_xml(archive: zipfile.ZipFile, name: str) -> ElementTree.Element | None:
    try:
        payload = archive.read(name)
    except KeyError:
        return None
    return ElementTree.fromstring(payload)


def _level_formats(root: ElementTree.Element | None) -> dict[str, dict[str, str]]:
    """Map abstractNumId -> {level: number format}."""
    formats: dict[str, dict[str, str]] = {}
    if root is None:
        return formats
    for abstract in root.findall(W_ABSTRACT_NUM):
        abstract_id = _value(abstract, "abstractNumId")
        levels: dict[str, str] = {}
        for level in abstract.findall(W_LVL):
            num_format = _child(level, "numFmt")
            if num_format is not None:
                levels[_value(level, "ilvl")] = _value(num_format, "val")
        formats[abstract_id] = levels
    return formats


def _number_map(root: ElementTree.Element | None) -> dict[str, str]:
    """Map numId -> abstractNumId."""
    mapping: dict[str, str] = {}
    if root is None:
        return mapping
    for number in root.findall(W_NUM):
        abstract = _child(number, "abstractNumId")
        if abstract is not None:
            mapping[_value(number, "numId")] = _value(abstract, "val")
    return mapping


def _direct_numbering(
    element: ElementTree.Element | None,
) -> tuple[str, str] | None:
    """Return (numId, ilvl) from a w:numPr, or None when absent or disabled."""
    num_pr = element
    if num_pr is not None and num_pr.tag != W_NUMPR:
        num_pr = _child(num_pr, "numPr")
    if num_pr is None:
        return None
    num_id = _value(_child(num_pr, "numId"), "val")
    if not num_id or num_id == "0":
        # numId 0 is Word's explicit "no numbering".
        return None
    level = _value(_child(num_pr, "ilvl"), "val") or "0"
    return num_id, level


def _style_numbering(
    root: ElementTree.Element | None,
) -> dict[str, tuple[str, str, str]]:
    """Map styleId -> (numId, ilvl, basedOn) for styles that carry numbering."""
    styles: dict[str, tuple[str, str, str]] = {}
    if root is None:
        return styles
    for style in root.findall(W_STYLE):
        style_id = _value(style, "styleId")
        if not style_id:
            continue
        based_on = _value(_child(style, "basedOn"), "val")
        direct = _direct_numbering(_child(style, "pPr"))
        if direct is None:
            styles[style_id] = ("", "", based_on)
            continue
        num_id, level = direct
        styles[style_id] = (num_id, level, based_on)
    return styles


def _resolve_style(
    style_id: str, styles: dict[str, tuple[str, str, str]]
) -> tuple[str, str] | None:
    """Walk the basedOn chain until a style contributes numbering."""
    seen: set[str] = set()
    current = style_id
    for _ in range(STYLE_CHAIN_LIMIT):
        if not current or current in seen:
            return None
        seen.add(current)
        entry = styles.get(current)
        if entry is None:
            return None
        num_id, level, based_on = entry
        if num_id:
            return num_id, level
        current = based_on
    return None


def _paragraph_text(paragraph: ElementTree.Element) -> str:
    parts = [node.text or "" for node in paragraph.iter(W_T)]
    text = " ".join(" ".join(parts).split())
    if len(text) > SNIPPET_LIMIT:
        return text[:SNIPPET_LIMIT] + "..."
    return text


def _resolve_format(
    num_id: str, level: str, levels: dict[str, dict[str, str]], numbers: dict[str, str]
) -> str:
    abstract_id = numbers.get(num_id, "")
    by_level = levels.get(abstract_id, {})
    return by_level.get(level) or by_level.get("0") or ""


def scan_docx(path: Path) -> DocxResult:
    """Scan one ``.docx`` file and return its bullet-numbered paragraphs."""
    result = DocxResult()
    with zipfile.ZipFile(path) as archive:
        document = _read_xml(archive, DOCUMENT_PART)
        if document is None:
            raise ValueError(f"{path}: missing {DOCUMENT_PART}")
        numbering = _read_xml(archive, NUMBERING_PART)
        levels = _level_formats(numbering)
        numbers = _number_map(numbering)
        styles = _style_numbering(_read_xml(archive, STYLES_PART))

    for index, paragraph in enumerate(document.iter(W_P), start=1):
        result.paragraphs += 1
        paragraph_properties = _child(paragraph, "pPr")

        resolved = _direct_numbering(
            _child(paragraph_properties, "numPr")
            if paragraph_properties is not None
            else None
        )
        source = "direct numPr"
        if resolved is None and paragraph_properties is not None:
            style_id = _value(_child(paragraph_properties, "pStyle"), "val")
            if style_id:
                inherited = _resolve_style(style_id, styles)
                if inherited is not None:
                    resolved = inherited
                    source = f"style {style_id}"
        if resolved is None:
            continue

        result.numbered += 1
        num_id, level = resolved
        if _resolve_format(num_id, level, levels, numbers) != BULLET_FORMAT:
            continue
        result.findings.append(
            ParagraphFinding(
                index=index,
                num_id=num_id,
                level=level,
                source=source,
                text=_paragraph_text(paragraph),
            )
        )
    return result


def _docx_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    yield from sorted(path.rglob("*.docx"))


def _write_json(
    stdout: TextIO, records: list[dict[str, object]], bullets: int
) -> None:
    payload = {
        "tool": "check_docx_numbering",
        "version": __version__,
        "files": records,
        "summary": {
            "files": len(records),
            "findings": bullets,
        },
    }
    json.dump(payload, stdout, ensure_ascii=False, indent=2)
    stdout.write("\n")


def run(
    paths: Iterable[str],
    *,
    output_format: str = "text",
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Scan every path and return the process exit code."""
    records: list[dict[str, object]] = []
    findings = 0
    problems: list[str] = []

    for value in list(paths):
        path = Path(value)
        if not path.exists():
            print(f"{value}: path does not exist", file=stderr)
            problems.append(value)
            continue
        for candidate in _docx_files(path):
            try:
                result = scan_docx(candidate)
            except (
                OSError,
                ValueError,
                zipfile.BadZipFile,
                ElementTree.ParseError,
            ) as error:
                print(f"{candidate}: {error}", file=stderr)
                problems.append(str(candidate))
                continue
            findings += len(result.findings)
            if output_format == "json":
                records.append({"path": str(candidate), **result.as_dict()})
            else:
                for finding in result.findings:
                    print(finding.format(str(candidate)), file=stdout)

    if output_format == "json":
        _write_json(stdout, records, findings)

    if problems:
        return EXIT_ERROR
    if findings:
        return EXIT_FINDINGS
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_docx_numbering",
        description="Report Word paragraphs that carry bullet numbering.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help=".docx files or directories to scan (default: .)",
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
    return run(args.paths, output_format=args.output_format)


if __name__ == "__main__":
    raise SystemExit(main())
