#!/usr/bin/env python3
"""剥除 Markdown 无序列表标记。

块状态机顺序（方案 v3.1 §3.1），禁止对全文做天真逐行替换：

1. 文件起始的 front matter 整段不改写。YAML 用 ``---`` 开始，用 ``---`` 或 ``...``
   结束；TOML 用 ``+++`` 开始并用同样的 ``+++`` 结束。中间不能有空行，闭合标记必须
   出现在开标记之后的 200 行以内。否则不当作 front matter，避免吞掉正文列表。
2. 抑制区与 front matter 共用同一种不改写区域。成对的
   ``<!-- no-markdown-bullets: off reason="..." -->`` /
   ``<!-- no-markdown-bullets: on reason="..." -->`` 之间原样保留。
   ``reason`` 必填且去空白后非空。抑制区不嵌套。未闭合则保留到 EOF，退出码 2。
   已开启的围栏、HTML 原始块、front matter、缩进代码里的指令无效。
   行首只认 0 到 3 列；四格空格或一个 Tab 是缩进代码，不开启抑制区。
3. 围栏 ``` / ~~~：记录字符与长度；CommonMark 不嵌套。引用深度变浅时，引用内的
   围栏随引用结束，不把后面的正文算进代码。真正未闭合才跳到 EOF 并告警。
   容器内先剥掉引用前缀和列表内容缩进，再判断开闭。
4. HTML 原始块整块不改。pre/script/style/textarea、注释、处理指令、声明、CDATA
   未闭合时跳到 EOF 并告警；块级标签直到空行（空行本身原样输出）。
5. 表格整块不改，包含单元格里的 ``-``。
6. 主题分隔线（``---`` / ``***`` / ``* * *`` / ``- - -`` / ``+ + +`` 以及下划线）先于 UL 识别。
7. 列表紧邻续行优先于缩进代码。引用深度变化时，丢掉不属于当前引用层的列表帧：
   进入更深引用会结束外侧列表，回到更浅处会结束深处的列表。
   只有非列表上下文，且绝对缩进 ≥4 空格或 1 个 Tab，才保护为缩进代码。空行中断紧邻续行。
8. 其余 UL、空列表项、任务列表剥掉标记。任务框 ``[ ]`` / ``[x]`` / ``[X]`` 一并去掉，
   不宣称保留勾选。

剥完后用同一套规则重解析。结果里仍有待剥 UL，或剥完后新产生跳过区，退出码 1。
有跳过且结果没有残留 UL，退出码 2。否则退出码 0。正文幂等：退出码 0 或 2 时再跑一次正文不变。

JSON 报告只走 ``--report`` 文件或 stderr，不写进 stdout。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

__version__ = "3.1.0"


UL_MARKERS = "-*+"
THEMATIC_MARKERS = "-*+_"
BLOCK_TAGS = sorted(
    {
        "address",
        "article",
        "aside",
        "base",
        "basefont",
        "blockquote",
        "body",
        "caption",
        "center",
        "col",
        "colgroup",
        "dd",
        "details",
        "dialog",
        "dir",
        "div",
        "dl",
        "dt",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "frame",
        "frameset",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "head",
        "header",
        "hr",
        "html",
        "iframe",
        "legend",
        "li",
        "link",
        "main",
        "menu",
        "menuitem",
        "nav",
        "noframes",
        "ol",
        "optgroup",
        "option",
        "p",
        "param",
        "search",
        "section",
        "source",
        "summary",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "title",
        "tr",
        "track",
        "ul",
    },
    key=len,
    reverse=True,
)

QUOTE_RE = re.compile(r"^ {0,3}> ?")
OL_RE = re.compile(r"^(\d{1,9}[.)])(.*)$")
FRONTMATTER_MAX_LINES = 200
SUPPRESSION_RE = re.compile(
    r"^<!--\s*no-markdown-bullets:\s*(off|on)\b(.*?)-->\s*$"
)
SUPPRESSION_REASON_RE = re.compile(r"""reason\s*=\s*("[^"]*"|'[^']*')""")
FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})(.*)$")
HTML_TYPE1_RE = re.compile(r"^<(pre|script|style|textarea)(?:[\s>]|$)", re.IGNORECASE)
HTML_TYPE6_RE = re.compile(
    r"^</?(?:" + "|".join(BLOCK_TAGS) + r")(?:[\s/>]|$)",
    re.IGNORECASE,
)
HTML_DECL_RE = re.compile(r"^<![A-Z]")
TASK_RE = re.compile(r"^\[([ xX])\](.*)$")
DELIM_CELL_RE = re.compile(r"\s*:?-{1,}:?\s*")


@dataclass
class ListFrame:
    marker_indent: int
    content_indent: int
    kind: str
    quote_depth: int


@dataclass
class FenceState:
    char: str
    length: int
    start_line: int
    quote_depth: int
    base_indent: int


@dataclass
class HtmlState:
    mode: str
    token: str
    start_line: int


@dataclass
class Region:
    """一段不改写区域。front matter 与抑制区共用这个标记。"""

    kind: str
    start_line: int
    end_line: int | None
    reason: str = ""
    closed: bool = True

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "reason": self.reason,
            "closed": self.closed,
        }


@dataclass
class _Directive:
    action: str
    reason: str


@dataclass
class RunData:
    text: str
    stripped_lines: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    regions: list[dict[str, object]] = field(default_factory=list)
    suppressed_lines: int = 0
    suppression_blocks: int = 0


@dataclass
class StripResult:
    """``strip_text`` 的结果。退出码含义见模块说明。"""

    text: str
    exit_code: int
    diagnostics: list[str]
    stripped_lines: list[int]
    warnings: list[str]
    regions: list[dict[str, object]] = field(default_factory=list)
    suppressed_lines: int = 0
    suppression_blocks: int = 0


def split_keep_ends(text: str) -> list[tuple[str, str]]:
    """按行切开，并保留每一行原来的结尾（``\\n``、``\\r\\n``、``\\r`` 或空）。"""
    lines: list[tuple[str, str]] = []
    i = 0
    n = len(text)
    while i < n:
        j = i
        while j < n and text[j] not in "\r\n":
            j += 1
        body = text[i:j]
        if j >= n:
            lines.append((body, ""))
            break
        if text[j] == "\r" and j + 1 < n and text[j + 1] == "\n":
            lines.append((body, "\r\n"))
            i = j + 2
        elif text[j] == "\r":
            lines.append((body, "\r"))
            i = j + 1
        else:
            lines.append((body, "\n"))
            i = j + 1
    return lines


def join_lines(lines: list[tuple[str, str]]) -> str:
    return "".join(body + ending for body, ending in lines)


def peel_quotes(body: str) -> tuple[str, str, int]:
    """返回（原文引用前缀、剥掉引用后的剩余、引用层数）。"""
    prefix = ""
    rest = body
    depth = 0
    while True:
        match = QUOTE_RE.match(rest)
        if not match:
            return prefix, rest, depth
        prefix += match.group(0)
        rest = rest[match.end() :]
        depth += 1


def measure_indent(text: str) -> tuple[int, int]:
    """返回（缩进列数，缩进结束下标）。Tab 停在 4 列。"""
    cols = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char == " ":
            cols += 1
            index += 1
        elif char == "\t":
            cols += 4 - (cols % 4)
            index += 1
        else:
            break
    return cols, index


def take_columns(text: str, columns: int) -> tuple[str, str]:
    """从行首拿走恰好 ``columns`` 列。Tab 会越过边界时停在 Tab 之前。"""
    if columns <= 0:
        return "", text
    cols = 0
    index = 0
    while index < len(text) and cols < columns:
        char = text[index]
        if char == " ":
            step = 1
        elif char == "\t":
            step = 4 - (cols % 4)
        else:
            break
        if cols + step > columns:
            break
        cols += step
        index += 1
    return text[:index], text[index:]


def advance_col(col: int, text: str) -> int:
    for char in text:
        if char == "\t":
            col += 4 - (col % 4)
        else:
            col += 1
    return col


def is_thematic_break(rest: str) -> bool:
    cols, index = measure_indent(rest)
    if cols >= 4:
        return False
    raw = rest[index:].strip(" \t")
    if not raw:
        return False
    marker = ""
    count = 0
    for char in raw:
        if char in " \t":
            continue
        if char not in THEMATIC_MARKERS:
            return False
        if not marker:
            marker = char
        elif char != marker:
            return False
        count += 1
    return count >= 3


def parse_ul(after: str) -> tuple[str, str, str, str] | None:
    if not after or after[0] not in UL_MARKERS:
        return None
    marker = after[0]
    index = 1
    if index < len(after) and after[index] not in " \t":
        return None
    while index < len(after) and after[index] in " \t":
        index += 1
    content = after[index:]
    if content.strip(" \t") == "":
        content = ""
    return ("ul", marker, after[1:index], content)


def parse_ol(after: str) -> tuple[str, str, str, str] | None:
    match = OL_RE.match(after)
    if not match:
        return None
    marker = match.group(1)
    rest = match.group(2)
    if rest == "":
        return ("ol", marker, "", "")
    if rest[0] not in " \t":
        return None
    index = 0
    while index < len(rest) and rest[index] in " \t":
        index += 1
    content = rest[index:]
    if content.strip(" \t") == "":
        content = ""
    return ("ol", marker, rest[:index], content)


def strip_task(content: str) -> str:
    """去掉 GFM 任务框。没有任务框时原样返回。"""
    match = TASK_RE.match(content)
    if not match:
        return content
    rest = match.group(2)
    if rest == "":
        return ""
    if rest[0] not in " \t":
        return content
    return rest.lstrip(" \t")


def content_indent_of(marker_indent: int, marker: str, whitespace: str) -> int:
    col = advance_col(marker_indent, marker)
    if whitespace == "":
        return col + 1
    return advance_col(col, whitespace)


def match_fence_open(rel_text: str) -> tuple[str, int] | None:
    cols, index = measure_indent(rel_text)
    if cols > 3:
        return None
    match = FENCE_OPEN_RE.match(rel_text[index:])
    if not match:
        return None
    token = match.group(1)
    info = match.group(2)
    if token[0] == "`" and "`" in info:
        return None
    return token[0], len(token)


def match_fence_close(rel_text: str, char: str, length: int) -> bool:
    cols, index = measure_indent(rel_text)
    if cols > 3:
        return False
    after = rel_text[index:].strip(" \t")
    return len(after) >= length and set(after) == {char}


def match_html(rel_text: str) -> tuple[str, str] | None:
    cols, index = measure_indent(rel_text)
    if cols > 3:
        return None
    text = rel_text[index:]
    if not text.startswith("<"):
        return None
    type1 = HTML_TYPE1_RE.match(text)
    if type1:
        return ("token", f"</{type1.group(1).lower()}>")
    if text.startswith("<!--"):
        return ("token", "-->")
    if text.startswith("<?"):
        return ("token", "?>")
    if text.startswith("<![CDATA["):
        return ("token", "]]>")
    if HTML_DECL_RE.match(text):
        return ("token", ">")
    if HTML_TYPE6_RE.match(text):
        return ("blank", "")
    return None


def is_delimiter_row(rest: str) -> bool:
    stripped = rest.strip(" \t")
    if "|" not in stripped:
        return False
    core = stripped[1:] if stripped.startswith("|") else stripped
    if core.endswith("|"):
        core = core[:-1]
    if core == "":
        return False
    cells = core.split("|")
    return all(DELIM_CELL_RE.fullmatch(cell) is not None for cell in cells)


def _front_matter_token(body: str) -> str:
    return body.rstrip(" \t")


def front_matter_span(lines: list[tuple[str, str]]) -> int:
    """返回 front matter 占用的行数。不能安全判定时返回 0。

    开标记必须是文件第一行的 ``---``（YAML）或 ``+++``（TOML）。
    YAML 可以用 ``---`` 或 ``...`` 闭合，TOML 只能用同样的 ``+++``。
    中间出现空行，或闭合标记不在开标记之后的 200 行以内，就整段放弃。
    """
    if not lines:
        return 0
    opening = _front_matter_token(lines[0][0])
    if opening not in ("---", "+++"):
        return 0
    limit = min(len(lines), FRONTMATTER_MAX_LINES + 1)
    for index in range(1, limit):
        token = _front_matter_token(lines[index][0])
        if token == "":
            return 0
        if opening == "---" and token in ("---", "..."):
            return index + 1
        if token == opening:
            return index + 1
    return 0


def match_directive(body: str) -> _Directive | None:
    """识别抑制指令。不是指令时返回 None；reason 缺失时 ``reason`` 为空串。

    引用前缀先剥掉。剩下的行首按列计，超过 3 列（四格空格或一个 Tab）
    是缩进代码，不当指令。
    """
    _prefix, rest, _depth = peel_quotes(body)
    cols, index = measure_indent(rest)
    if cols > 3:
        return None
    content = rest[index:]
    if not content.startswith("<!--"):
        return None
    match = SUPPRESSION_RE.match(content)
    if match is None:
        return None
    reason_match = SUPPRESSION_REASON_RE.search(match.group(2) or "")
    reason = ""
    if reason_match is not None:
        reason = reason_match.group(1)[1:-1].strip()
    return _Directive(match.group(1), reason)


class _Parser:
    def __init__(self, lines: list[tuple[str, str]]) -> None:
        self.lines = lines
        self.out: list[tuple[str, str]] = []
        self.stripped_lines: list[int] = []
        self.warnings: list[str] = []
        self.stack: list[ListFrame] = []
        self.tight = False
        self.in_code = False
        self.fence: FenceState | None = None
        self.html: HtmlState | None = None
        self.regions: list[Region] = []
        self.hold: Region | None = None
        self.suppressed_lines = 0
        self.suppression_blocks = 0

    def run(self) -> RunData:
        start = front_matter_span(self.lines)
        if start:
            self.regions.append(Region("frontmatter", 1, start, "", True))
        self.out.extend(self.lines[:start])
        index = start
        while index < len(self.lines):
            index = self._step(index)
        if self.fence is not None:
            self.warnings.append(
                "warning: unclosed fence at line "
                f"{self.fence.start_line}; skipping through EOF"
            )
        if self.html is not None and self.html.mode == "token":
            self.warnings.append(
                "warning: unclosed html block at line "
                f"{self.html.start_line}; skipping through EOF"
            )
        if self.hold is not None:
            self.warnings.append(
                "warning: unclosed suppression at line "
                f"{self.hold.start_line}; keeping through EOF"
            )
        return RunData(
            join_lines(self.out),
            self.stripped_lines,
            self.warnings,
            [region.as_dict() for region in self.regions],
            self.suppressed_lines,
            self.suppression_blocks,
        )

    def _step(self, index: int) -> int:
        body, _ending = self.lines[index]
        if self.fence is not None:
            _prefix, rest, quote_depth = peel_quotes(body)
            if quote_depth < self.fence.quote_depth:
                # 引用结束时，里面没闭合的围栏也结束，当前行重新按正文处理。
                self.fence = None
            else:
                if quote_depth == self.fence.quote_depth:
                    _taken, rel = take_columns(rest, self.fence.base_indent)
                    if match_fence_close(rel, self.fence.char, self.fence.length):
                        self.fence = None
                self.out.append(self.lines[index])
                return index + 1

        if self.html is not None:
            self.out.append(self.lines[index])
            if self.html.mode == "blank" and body.strip(" \t") == "":
                self.html = None
                self.tight = False
                self.stack.clear()
                self.in_code = False
            elif self.html.mode == "token" and self.html.token in body.lower():
                self.html = None
            return index + 1

        if self.hold is not None:
            self._hold_suppression(index, body)
            return index + 1

        if body.strip(" \t") == "":
            self.out.append(self.lines[index])
            self.tight = False
            self.stack.clear()
            if self.in_code and not self._next_nonblank_is_code(index + 1):
                self.in_code = False
            return index + 1

        prefix, rest, quote_depth = peel_quotes(body)
        self._sync_quote_lists(quote_depth)
        cols, _indent_end = measure_indent(rest)
        if self.in_code and cols >= 4:
            self.out.append(self.lines[index])
            return index + 1
        if self.in_code:
            self.in_code = False
        if self._try_open_suppression(index, body):
            return index + 1

        if self._try_table(index):
            return self._table_end

        if self._try_open_fence(index, rest, quote_depth):
            return index + 1
        if self._try_open_html(index, rest, quote_depth):
            return index + 1
        if is_thematic_break(rest):
            self.stack.clear()
            self.tight = False
            self.in_code = False
            self.out.append(self.lines[index])
            return index + 1

        cols, indent_end = measure_indent(rest)
        if not self.tight and cols >= 4:
            self.in_code = True
            self.stack.clear()
            self.out.append(self.lines[index])
            return index + 1

        self._handle_line(index, prefix, rest, quote_depth, cols, indent_end)
        return index + 1

    def _sync_quote_lists(self, quote_depth: int) -> None:
        """丢掉不属于当前引用层的列表帧。

        进入更深的引用时，外侧列表结束。回到更浅处时，深处的列表结束。
        同一层的嵌套列表保留。
        """
        if not self.stack:
            return
        if all(frame.quote_depth == quote_depth for frame in self.stack):
            return
        self.stack = [
            frame for frame in self.stack if frame.quote_depth == quote_depth
        ]
        if not self.stack:
            self.tight = False

    def _try_open_suppression(self, index: int, body: str) -> bool:
        directive = match_directive(body)
        if directive is None or directive.action != "off" or not directive.reason:
            return False
        region = Region("suppression", index + 1, None, directive.reason, False)
        self.regions.append(region)
        self.hold = region
        self.suppression_blocks += 1
        self.in_code = False
        self.out.append(self.lines[index])
        return True

    def _hold_suppression(self, index: int, body: str) -> None:
        """抑制区内原样抄写。只有带非空 reason 的 on 能结束，不增加嵌套层。"""
        directive = match_directive(body)
        if (
            self.hold is not None
            and directive is not None
            and directive.action == "on"
            and directive.reason
        ):
            self.hold.end_line = index + 1
            self.hold.closed = True
            self.hold = None
        else:
            self.suppressed_lines += 1
        self.out.append(self.lines[index])

    def _next_nonblank_is_code(self, start: int) -> bool:
        index = start
        while index < len(self.lines):
            body = self.lines[index][0]
            if body.strip(" \t") == "":
                index += 1
                continue
            _prefix, rest, _quote_depth = peel_quotes(body)
            cols, _indent_end = measure_indent(rest)
            return cols >= 4
        return False

    def _try_table(self, index: int) -> bool:
        body = self.lines[index][0]
        _prefix, rest, _quote_depth = peel_quotes(body)
        if "|" not in rest or index + 1 >= len(self.lines):
            return False
        _prefix2, rest2, _quote2 = peel_quotes(self.lines[index + 1][0])
        if not is_delimiter_row(rest2):
            return False
        end = index + 2
        while end < len(self.lines):
            row = self.lines[end][0]
            if row.strip(" \t") == "":
                break
            _prefix_row, rest_row, _quote_row = peel_quotes(row)
            if "|" not in rest_row:
                break
            end += 1
        self.out.extend(self.lines[index:end])
        self.stack.clear()
        self.tight = False
        self.in_code = False
        self._table_end = end
        return True

    def _list_base(self, rest: str, quote_depth: int) -> int:
        if not (self.tight and self.stack and self.stack[-1].quote_depth == quote_depth):
            return 0
        cols, _indent_end = measure_indent(rest)
        frame = self.stack[-1]
        if cols >= frame.content_indent:
            return frame.content_indent
        return 0

    def _try_open_fence(self, index: int, rest: str, quote_depth: int) -> bool:
        base = self._list_base(rest, quote_depth)
        _taken, rel = take_columns(rest, base)
        opened = match_fence_open(rel)
        if opened is None:
            return False
        char, length = opened
        self.fence = FenceState(char, length, index + 1, quote_depth, base)
        self.in_code = False
        self.out.append(self.lines[index])
        return True

    def _try_open_html(self, index: int, rest: str, quote_depth: int) -> bool:
        base = self._list_base(rest, quote_depth)
        _taken, rel = take_columns(rest, base)
        opened = match_html(rel)
        if opened is None:
            return False
        mode, token = opened
        self.in_code = False
        self.out.append(self.lines[index])
        if mode == "token" and token in self.lines[index][0].lower():
            self.html = None
        else:
            self.html = HtmlState(mode, token, index + 1)
        return True

    def _handle_line(
        self,
        index: int,
        prefix: str,
        rest: str,
        quote_depth: int,
        cols: int,
        indent_end: int,
    ) -> None:
        after = rest[indent_end:]
        marker = parse_ul(after) or parse_ol(after)
        in_continuation = self.tight and bool(self.stack)
        if marker is not None:
            kind, marker_text, whitespace, content = marker
            position = self._place_marker(cols, quote_depth)
            if position is not None:
                self._commit_marker(
                    index,
                    position,
                    kind,
                    marker_text,
                    whitespace,
                    content,
                    cols,
                    quote_depth,
                    prefix,
                    rest,
                    indent_end,
                )
                return
        if in_continuation:
            self.out.append(self.lines[index])
            return
        self.stack.clear()
        self.tight = False
        self.out.append(self.lines[index])

    def _place_marker(self, cols: int, quote_depth: int) -> str | None:
        while self.stack and self.stack[-1].quote_depth > quote_depth:
            self.stack.pop()
        while True:
            if not self.stack or self.stack[-1].quote_depth != quote_depth:
                if cols < 4:
                    return "top"
                return None
            frame = self.stack[-1]
            if cols == frame.marker_indent:
                return "sibling"
            if frame.content_indent <= cols < frame.content_indent + 4:
                return "nested"
            if cols < frame.marker_indent:
                self.stack.pop()
                continue
            return None

    def _commit_marker(
        self,
        index: int,
        position: str,
        kind: str,
        marker_text: str,
        whitespace: str,
        content: str,
        cols: int,
        quote_depth: int,
        prefix: str,
        rest: str,
        indent_end: int,
    ) -> None:
        if position == "sibling":
            self.stack.pop()
        frame = ListFrame(
            cols,
            content_indent_of(cols, marker_text, whitespace),
            kind,
            quote_depth,
        )
        self.stack.append(frame)
        self.tight = True
        self.in_code = False
        if kind != "ul":
            self.out.append(self.lines[index])
            return
        stripped = strip_task(content)
        body = prefix if stripped == "" else prefix + rest[:indent_end] + stripped
        ending = self.lines[index][1]
        self.out.append((body, ending))
        self.stripped_lines.append(index + 1)


def _run(text: str) -> RunData:
    return _Parser(split_keep_ends(text)).run()


def strip_text(text: str) -> StripResult:
    """剥除 ``text`` 中的 Markdown UL，不读写文件。"""
    first = _run(text)
    second = _run(first.text)
    diagnostics = list(first.warnings)
    if second.stripped_lines:
        exit_code = 1
        for line_no in second.stripped_lines:
            diagnostics.append(
                f"error: residual unordered list at output line {line_no}"
            )
    elif first.warnings:
        exit_code = 2
    elif second.warnings:
        exit_code = 1
        diagnostics.append(
            "error: strip created a skipped region; result is unfinished"
        )
    else:
        exit_code = 0
    listed = ",".join(str(line_no) for line_no in first.stripped_lines) or "-"
    diagnostics.append(f"info: stripped={len(first.stripped_lines)} lines={listed}")
    return StripResult(
        text=first.text,
        exit_code=exit_code,
        diagnostics=diagnostics,
        stripped_lines=list(first.stripped_lines),
        warnings=list(first.warnings),
        regions=list(first.regions),
        suppressed_lines=first.suppressed_lines,
        suppression_blocks=first.suppression_blocks,
    )


def _classify_diagnostic(line: str) -> tuple[str | None, int, int | None]:
    match = re.search(r"line (\d+)", line)
    line_no = int(match.group(1)) if match else None
    if "unclosed suppression" in line:
        return "unclosed-suppression", 2, line_no
    if "unclosed fence" in line:
        return "unclosed-fence", 2, line_no
    if "unclosed html" in line:
        return "unclosed-html", 2, line_no
    if "residual unordered list" in line:
        return "residual-unordered-list", 1, line_no
    if "created a skipped region" in line:
        return "created-skip", 1, line_no
    return None, 0, None


def build_report(result: StripResult, source: str) -> dict[str, object]:
    """机读报告。调用方必须把它写到文件或 stderr，不能写到 stdout。"""
    findings: list[dict[str, object]] = []
    for line_no in result.stripped_lines:
        findings.append({"line": line_no, "code": "stripped", "exit_class": 0})
    for line in result.diagnostics:
        code, exit_class, found = _classify_diagnostic(line)
        if code is None:
            continue
        findings.append({"line": found, "code": code, "exit_class": exit_class})
    return {
        "tool": "strip_md_ul",
        "version": __version__,
        "source": source,
        "exit_code": result.exit_code,
        "stripped_lines": list(result.stripped_lines),
        "warnings": list(result.warnings),
        "diagnostics": list(result.diagnostics),
        "regions": list(result.regions),
        "summary": {
            "exit_code": result.exit_code,
            "stripped": len(result.stripped_lines),
            "suppression_blocks": result.suppression_blocks,
            "suppressed_lines": result.suppressed_lines,
        },
        "findings": findings,
    }


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(f"error: {message}", file=sys.stderr)
        self.exit(1)


def _read_text(path: str | None) -> str:
    if path is None or path == "-":
        data = sys.stdin.buffer.read()
        label = "<stdin>"
    else:
        file_path = Path(path)
        if not file_path.is_file():
            raise OSError(f"{path}: not a file")
        data = file_path.read_bytes()
        label = path
    try:
        return data.decode("utf-8")
    except UnicodeError as exc:
        raise OSError(f"{label}: utf-8 decode failed: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = _ArgumentParser(
        prog="strip_md_ul.py",
        description=(
            "剥除 Markdown 无序列表标记，结果写到 stdout，不修改源文件。"
            "退出码 0=结果无残留 UL，2=有跳过，1=失败。"
            "JSON 只通过 --report 写出，不进入 stdout。"
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Markdown 文件路径；省略或写成 - 时读取 stdin",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="只做判定，不把正文写到 stdout；退出码与默认改写相同",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="把改写结果写到 stdout，并在 stderr 标明未修改源文件",
    )
    parser.add_argument(
        "--report",
        metavar="PATH",
        help=(
            "把 JSON 报告写到 PATH。PATH 为 - 时写到 stderr，"
            "并且不再混入人类可读诊断。绝不写到 stdout。"
        ),
    )
    args = parser.parse_args(argv)
    if args.check and args.dry_run:
        print("error: --check 与 --dry-run 不能同时使用", file=sys.stderr)
        return 1
    try:
        text = _read_text(args.path)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    result = strip_text(text)
    if args.dry_run:
        result.diagnostics.append("info: dry-run source-not-modified")
    source = "<stdin>" if args.path is None or args.path == "-" else args.path
    if args.report is not None:
        payload = (
            json.dumps(build_report(result, source), ensure_ascii=False, indent=2)
            + "\n"
        ).encode("utf-8")
        if args.report == "-":
            sys.stderr.buffer.write(payload)
        else:
            try:
                Path(args.report).write_bytes(payload)
            except OSError as exc:
                print(f"error: {args.report}: {exc}", file=sys.stderr)
                return 1
            for line in result.diagnostics:
                print(line, file=sys.stderr)
    else:
        for line in result.diagnostics:
            print(line, file=sys.stderr)
    if not args.check:
        sys.stdout.buffer.write(result.text.encode("utf-8"))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
