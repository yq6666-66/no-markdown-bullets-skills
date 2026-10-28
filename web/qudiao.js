/* 去黑点 · Markdown 无序列表清理引擎
 * 与 reference 实现（no-markdown-bullets v3.3.2 strip_md_ul.py）保持规则对齐。
 * 纯函数，无依赖，可在浏览器与 Node 中运行。
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.QD = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var UL_MARKERS = '-*+';
  var THEMATIC_MARKERS = '-*_';
  var QUOTE_RE = /^ {0,3}> ?/;
  var OL_RE = /^(\d{1,9}[.)])(.*)$/;
  var FRONTMATTER_MAX_LINES = 200;
  var SUPPRESSION_RE = /^<!--\s*no-markdown-bullets:\s*(off|on)\b([\s\S]*?)-->\s*$/;
  var SUPPRESSION_REASON_RE = /reason\s*=\s*("[^"]*"|'[^']*')/;
  var FENCE_OPEN_RE = /^(`{3,}|~{3,})([\s\S]*)$/;
  var HTML_TYPE1_RE = /^<(pre|script|style|textarea)(?:[\s>]|$)/i;
  var HTML_DECL_RE = /^<![A-Z]/;
  var TASK_RE = /^\[([ xX])\]([\s\S]*)$/;
  var DELIM_CELL_RE = /^\s*:?-+:?\s*$/;

  var BLOCK_TAGS = ('address article aside base basefont blockquote body caption center col colgroup dd details dialog dir div dl dt ' +
    'fieldset figcaption figure footer form frame frameset h1 h2 h3 h4 h5 h6 head header hr html iframe legend li link main ' +
    'menu menuitem nav noframes ol optgroup option p param search section source summary table tbody td tfoot th thead title tr track ul')
    .split(' ').filter(Boolean);
  BLOCK_TAGS.sort(function (a, b) { return b.length - a.length; });
  var HTML_TYPE6_RE = new RegExp('^</?(?:' + BLOCK_TAGS.join('|') + ')(?:[\\s/>]|$)', 'i');

  /* ---------- 基础工具 ---------- */

  function splitKeepEnds(text) {
    var lines = [], i = 0, n = text.length;
    while (i < n) {
      var j = i;
      while (j < n && text[j] !== '\r' && text[j] !== '\n') j++;
      var body = text.slice(i, j);
      if (j >= n) { lines.push({ body: body, ending: '' }); break; }
      if (text[j] === '\r' && j + 1 < n && text[j + 1] === '\n') {
        lines.push({ body: body, ending: '\r\n' }); i = j + 2;
      } else if (text[j] === '\r') {
        lines.push({ body: body, ending: '\r' }); i = j + 1;
      } else {
        lines.push({ body: body, ending: '\n' }); i = j + 1;
      }
    }
    return lines;
  }

  function joinLines(lines) {
    var out = '';
    for (var i = 0; i < lines.length; i++) out += lines[i].body + lines[i].ending;
    return out;
  }

  function peelQuotes(body) {
    var prefix = '', rest = body, depth = 0;
    for (;;) {
      var m = QUOTE_RE.exec(rest);
      if (!m) return { prefix: prefix, rest: rest, depth: depth };
      prefix += m[0];
      rest = rest.slice(m[0].length);
      depth++;
    }
  }

  function measureIndent(text) {
    var cols = 0, index = 0;
    while (index < text.length) {
      var c = text[index];
      if (c === ' ') { cols++; index++; }
      else if (c === '\t') { cols += 4 - (cols % 4); index++; }
      else break;
    }
    return { cols: cols, index: index };
  }

  function takeColumns(text, columns) {
    if (columns <= 0) return ['', text];
    var cols = 0, index = 0;
    while (index < text.length && cols < columns) {
      var c = text[index], step;
      if (c === ' ') step = 1;
      else if (c === '\t') step = 4 - (cols % 4);
      else break;
      if (cols + step > columns) break;
      cols += step; index++;
    }
    return [text.slice(0, index), text.slice(index)];
  }

  function advanceCol(col, text) {
    for (var i = 0; i < text.length; i++) {
      col += text[i] === '\t' ? 4 - (col % 4) : 1;
    }
    return col;
  }

  function trimST(s) { return s.replace(/^[ \t]+/, '').replace(/[ \t]+$/, ''); }

  /* ---------- 行级判定 ---------- */

  function isThematicBreak(rest) {
    var m = measureIndent(rest);
    if (m.cols >= 4) return false;
    var raw = trimST(rest.slice(m.index));
    if (!raw) return false;
    var marker = '', count = 0;
    for (var i = 0; i < raw.length; i++) {
      var c = raw[i];
      if (c === ' ' || c === '\t') continue;
      if (THEMATIC_MARKERS.indexOf(c) === -1) return false;
      if (!marker) marker = c;
      else if (c !== marker) return false;
      count++;
    }
    return count >= 3;
  }

  function isPlusOnlyLine(rest) {
    var m = measureIndent(rest);
    if (m.cols >= 4) return false;
    var count = 0, seen = false;
    for (var i = m.index; i < rest.length; i++) {
      var c = rest[i];
      if (c === ' ' || c === '\t') continue;
      seen = true;
      if (c !== '+') return false;
      count++;
    }
    return seen && count >= 3;
  }

  function parseUl(after) {
    if (!after || UL_MARKERS.indexOf(after[0]) === -1) return null;
    var marker = after[0], index = 1;
    if (index < after.length && after[index] !== ' ' && after[index] !== '\t') return null;
    while (index < after.length && (after[index] === ' ' || after[index] === '\t')) index++;
    var content = after.slice(index);
    if (trimST(content) === '') content = '';
    return { kind: 'ul', marker: marker, whitespace: after.slice(1, index), content: content };
  }

  function parseOl(after) {
    var m = OL_RE.exec(after);
    if (!m) return null;
    var marker = m[1], rest = m[2];
    if (rest === '') return { kind: 'ol', marker: marker, whitespace: '', content: '' };
    if (rest[0] !== ' ' && rest[0] !== '\t') return null;
    var index = 0;
    while (index < rest.length && (rest[index] === ' ' || rest[index] === '\t')) index++;
    var content = rest.slice(index);
    if (trimST(content) === '') content = '';
    return { kind: 'ol', marker: marker, whitespace: rest.slice(0, index), content: content };
  }

  function stripTask(content) {
    var m = TASK_RE.exec(content);
    if (!m) return { content: content, hadTask: false };
    var rest = m[2];
    if (rest === '') return { content: '', hadTask: true };
    if (rest[0] !== ' ' && rest[0] !== '\t') return { content: content, hadTask: false };
    return { content: rest.replace(/^[ \t]+/, ''), hadTask: true };
  }

  function contentIndentOf(markerIndent, marker, whitespace) {
    var col = advanceCol(markerIndent, marker);
    if (whitespace === '') return col + 1;
    return advanceCol(col, whitespace);
  }

  function matchFenceOpen(relText) {
    var m0 = measureIndent(relText);
    if (m0.cols > 3) return null;
    var m = FENCE_OPEN_RE.exec(relText.slice(m0.index));
    if (!m) return null;
    var token = m[1], info = m[2];
    if (token[0] === '`' && info.indexOf('`') !== -1) return null;
    return { char: token[0], length: token.length };
  }

  function matchFenceClose(relText, char, length) {
    var m0 = measureIndent(relText);
    if (m0.cols > 3) return false;
    var after = trimST(relText.slice(m0.index));
    if (after.length < length) return false;
    for (var i = 0; i < after.length; i++) if (after[i] !== char) return false;
    return after.length > 0;
  }

  function matchHtml(relText) {
    var m0 = measureIndent(relText);
    if (m0.cols > 3) return null;
    var text = relText.slice(m0.index);
    if (text[0] !== '<') return null;
    var t1 = HTML_TYPE1_RE.exec(text);
    if (t1) return { mode: 'token', token: '</' + t1[1].toLowerCase() + '>' };
    if (text.indexOf('<!--') === 0) return { mode: 'token', token: '-->' };
    if (text.indexOf('<?') === 0) return { mode: 'token', token: '?>' };
    if (text.indexOf('<![CDATA[') === 0) return { mode: 'token', token: ']]>' };
    if (HTML_DECL_RE.test(text)) return { mode: 'token', token: '>' };
    if (HTML_TYPE6_RE.test(text)) return { mode: 'blank', token: '' };
    return null;
  }

  function isDelimiterRow(rest) {
    var s = trimST(rest);
    if (s.indexOf('|') === -1) return false;
    var core = s[0] === '|' ? s.slice(1) : s;
    if (core.length && core[core.length - 1] === '|') core = core.slice(0, -1);
    if (core === '') return false;
    var cells = core.split('|');
    for (var i = 0; i < cells.length; i++) if (!DELIM_CELL_RE.test(cells[i])) return false;
    return true;
  }

  function frontMatterSpan(lines) {
    if (!lines.length) return 0;
    var opening = lines[0].body.replace(/[ \t]+$/, '');
    if (opening !== '---' && opening !== '+++') return 0;
    var limit = Math.min(lines.length, FRONTMATTER_MAX_LINES + 1);
    for (var i = 1; i < limit; i++) {
      var token = lines[i].body.replace(/[ \t]+$/, '');
      if (token === '') return 0;
      if (opening === '---' && (token === '---' || token === '...')) return i + 1;
      if (token === opening) return i + 1;
    }
    return 0;
  }

  function matchDirective(body) {
    var q = peelQuotes(body);
    var m0 = measureIndent(q.rest);
    if (m0.cols > 3) return null;
    var content = q.rest.slice(m0.index);
    if (content.indexOf('<!--') !== 0) return null;
    var m = SUPPRESSION_RE.exec(content);
    if (!m) return null;
    var rm = SUPPRESSION_REASON_RE.exec(m[2] || '');
    var reason = rm ? rm[1].slice(1, -1).trim() : '';
    return { action: m[1], reason: reason };
  }

  /* ---------- 解析器 ---------- */

  function Parser(lines) {
    this.lines = lines;
    this.out = [];
    this.strippedLines = [];
    this.warnings = [];
    this.stack = [];
    this.tight = false;
    this.inCode = false;
    this.fence = null;
    this.html = null;
    this.hold = null;
    this.suppressedLines = 0;
    this.suppressionBlocks = 0;
    this.protectedBlocks = 0;
  }

  Parser.prototype.run = function () {
    var start = frontMatterSpan(this.lines);
    if (start) {
      this.protectedBlocks++;
      for (var k = 0; k < start; k++) this.out.push(this.lines[k]);
    }
    var index = start;
    while (index < this.lines.length) index = this.step(index);
    if (this.fence) this.warnings.push('未闭合的代码围栏，起始于第 ' + this.fence.startLine + ' 行；其后内容原样跳过');
    if (this.html && this.html.mode === 'token') this.warnings.push('未闭合的 HTML 块，起始于第 ' + this.html.startLine + ' 行；其后内容原样跳过');
    if (this.hold) this.warnings.push('未闭合的抑制区，起始于第 ' + this.hold.startLine + ' 行；保留到文件末尾');
    return {
      text: joinLines(this.out),
      strippedLines: this.strippedLines,
      warnings: this.warnings,
      suppressedLines: this.suppressedLines,
      suppressionBlocks: this.suppressionBlocks,
      protectedBlocks: this.protectedBlocks
    };
  };

  Parser.prototype.step = function (index) {
    var body = this.lines[index].body;

    if (this.fence) {
      var q = peelQuotes(body);
      if (q.depth < this.fence.quoteDepth) {
        this.fence = null;
      } else {
        if (q.depth === this.fence.quoteDepth) {
          var taken = takeColumns(q.rest, this.fence.baseIndent);
          if (matchFenceClose(taken[1], this.fence.char, this.fence.length)) this.fence = null;
        }
        this.out.push(this.lines[index]);
        return index + 1;
      }
    }

    if (this.html) {
      this.out.push(this.lines[index]);
      if (this.html.mode === 'blank' && trimST(body) === '') {
        this.html = null; this.tight = false; this.stack = []; this.inCode = false;
      } else if (this.html.mode === 'token' && body.toLowerCase().indexOf(this.html.token) !== -1) {
        this.html = null;
      }
      return index + 1;
    }

    if (this.hold) { this.holdSuppression(index, body); return index + 1; }

    if (trimST(body) === '') {
      this.out.push(this.lines[index]);
      this.tight = false;
      this.stack = [];
      if (this.inCode && !this.nextNonblankIsCode(index + 1)) this.inCode = false;
      return index + 1;
    }

    var peeled = peelQuotes(body);
    var prefix = peeled.prefix, rest = peeled.rest, quoteDepth = peeled.depth;
    this.syncQuoteLists(quoteDepth);
    var mi = measureIndent(rest);
    if (this.inCode && mi.cols >= 4) { this.out.push(this.lines[index]); return index + 1; }
    if (this.inCode) this.inCode = false;

    if (this.tryOpenSuppression(index, body)) return index + 1;

    var tableEnd = this.tryTable(index);
    if (tableEnd !== null) return tableEnd;

    if (this.tryOpenFence(index, rest, quoteDepth)) return index + 1;
    if (this.tryOpenHtml(index, rest, quoteDepth)) return index + 1;

    if (isPlusOnlyLine(rest)) {
      this.stack = []; this.tight = false; this.inCode = false;
      this.out.push({ body: '', ending: this.lines[index].ending });
      this.strippedLines.push(index + 1);
      return index + 1;
    }

    if (isThematicBreak(rest)) {
      this.stack = []; this.tight = false; this.inCode = false;
      this.out.push(this.lines[index]);
      return index + 1;
    }

    var mi2 = measureIndent(rest);
    if (!this.tight && mi2.cols >= 4) {
      this.inCode = true;
      this.protectedBlocks++;
      this.stack = [];
      this.out.push(this.lines[index]);
      return index + 1;
    }

    this.handleLine(index, prefix, rest, quoteDepth, mi2.cols, mi2.index);
    return index + 1;
  };

  Parser.prototype.syncQuoteLists = function (quoteDepth) {
    if (!this.stack.length) return;
    var allSame = true;
    for (var i = 0; i < this.stack.length; i++) if (this.stack[i].quoteDepth !== quoteDepth) { allSame = false; break; }
    if (allSame) return;
    this.stack = this.stack.filter(function (f) { return f.quoteDepth === quoteDepth; });
    if (!this.stack.length) this.tight = false;
  };

  Parser.prototype.tryOpenSuppression = function (index, body) {
    var d = matchDirective(body);
    if (!d || d.action !== 'off' || !d.reason) return false;
    this.hold = { startLine: index + 1, reason: d.reason };
    this.suppressionBlocks++;
    this.protectedBlocks++;
    this.inCode = false;
    this.out.push(this.lines[index]);
    return true;
  };

  Parser.prototype.holdSuppression = function (index, body) {
    var d = matchDirective(body);
    if (this.hold && d && d.action === 'on' && d.reason) {
      this.hold = null;
    } else {
      this.suppressedLines++;
    }
    this.out.push(this.lines[index]);
  };

  Parser.prototype.nextNonblankIsCode = function (start) {
    for (var i = start; i < this.lines.length; i++) {
      var body = this.lines[i].body;
      if (trimST(body) === '') continue;
      var q = peelQuotes(body);
      return measureIndent(q.rest).cols >= 4;
    }
    return false;
  };

  Parser.prototype.tryTable = function (index) {
    var body = this.lines[index].body;
    var q = peelQuotes(body);
    if (q.rest.indexOf('|') === -1 || index + 1 >= this.lines.length) return null;
    var q2 = peelQuotes(this.lines[index + 1].body);
    if (!isDelimiterRow(q2.rest)) return null;
    var end = index + 2;
    while (end < this.lines.length) {
      var row = this.lines[end].body;
      if (trimST(row) === '') break;
      var qr = peelQuotes(row);
      if (qr.rest.indexOf('|') === -1) break;
      end++;
    }
    for (var k = index; k < end; k++) this.out.push(this.lines[k]);
    this.stack = []; this.tight = false; this.inCode = false;
    this.protectedBlocks++;
    return end;
  };

  Parser.prototype.listBase = function (rest, quoteDepth) {
    if (!(this.tight && this.stack.length && this.stack[this.stack.length - 1].quoteDepth === quoteDepth)) return 0;
    var cols = measureIndent(rest).cols;
    var frame = this.stack[this.stack.length - 1];
    return cols >= frame.contentIndent ? frame.contentIndent : 0;
  };

  Parser.prototype.tryOpenFence = function (index, rest, quoteDepth) {
    var base = this.listBase(rest, quoteDepth);
    var rel = takeColumns(rest, base)[1];
    var opened = matchFenceOpen(rel);
    if (!opened) return false;
    this.fence = { char: opened.char, length: opened.length, startLine: index + 1, quoteDepth: quoteDepth, baseIndent: base };
    this.inCode = false;
    this.protectedBlocks++;
    this.out.push(this.lines[index]);
    return true;
  };

  Parser.prototype.tryOpenHtml = function (index, rest, quoteDepth) {
    var base = this.listBase(rest, quoteDepth);
    var rel = takeColumns(rest, base)[1];
    var opened = matchHtml(rel);
    if (!opened) return false;
    this.inCode = false;
    this.protectedBlocks++;
    this.out.push(this.lines[index]);
    if (opened.mode === 'token' && this.lines[index].body.toLowerCase().indexOf(opened.token) !== -1) {
      this.html = null;
    } else {
      this.html = { mode: opened.mode, token: opened.token, startLine: index + 1 };
    }
    return true;
  };

  Parser.prototype.handleLine = function (index, prefix, rest, quoteDepth, cols, indentEnd) {
    var after = rest.slice(indentEnd);
    var marker = parseUl(after) || parseOl(after);
    var inContinuation = this.tight && this.stack.length > 0;
    if (marker) {
      var position = this.placeMarker(cols, quoteDepth);
      if (position) {
        this.commitMarker(index, position, marker, cols, quoteDepth, prefix, rest, indentEnd);
        return;
      }
    }
    if (inContinuation) { this.out.push(this.lines[index]); return; }
    this.stack = []; this.tight = false;
    this.out.push(this.lines[index]);
  };

  Parser.prototype.placeMarker = function (cols, quoteDepth) {
    while (this.stack.length && this.stack[this.stack.length - 1].quoteDepth > quoteDepth) this.stack.pop();
    for (;;) {
      if (!this.stack.length || this.stack[this.stack.length - 1].quoteDepth !== quoteDepth) {
        return cols < 4 ? 'top' : null;
      }
      var frame = this.stack[this.stack.length - 1];
      if (cols === frame.markerIndent) return 'sibling';
      if (frame.contentIndent <= cols && cols < frame.contentIndent + 4) return 'nested';
      if (cols < frame.markerIndent) { this.stack.pop(); continue; }
      return null;
    }
  };

  Parser.prototype.commitMarker = function (index, position, marker, cols, quoteDepth, prefix, rest, indentEnd) {
    if (position === 'sibling') this.stack.pop();
    this.stack.push({
      markerIndent: cols,
      contentIndent: contentIndentOf(cols, marker.marker, marker.whitespace),
      kind: marker.kind,
      quoteDepth: quoteDepth
    });
    this.tight = true;
    this.inCode = false;
    if (marker.kind !== 'ul') { this.out.push(this.lines[index]); return; }
    var t = stripTask(marker.content);
    var body = t.content === '' ? prefix : prefix + rest.slice(0, indentEnd) + t.content;
    this.out.push({ body: body, ending: this.lines[index].ending });
    this.strippedLines.push(index + 1);
  };

  /* ---------- 对外接口 ---------- */

  function runOnce(text) {
    return new Parser(splitKeepEnds(text)).run();
  }

  function strip(text) {
    var first = runOnce(text);
    var second = runOnce(first.text);
    var exitCode = 0;
    var errors = [];
    if (second.strippedLines.length) {
      exitCode = 1;
      errors.push('清理后仍有 ' + second.strippedLines.length + ' 处残留圆点');
    } else if (first.warnings.length) {
      exitCode = 2;
    } else if (second.warnings.length) {
      exitCode = 1;
      errors.push('清理过程产生了新的跳过区域');
    }
    return {
      text: first.text,
      source: text,
      exitCode: exitCode,
      strippedLines: first.strippedLines,
      warnings: first.warnings,
      errors: errors,
      suppressedLines: first.suppressedLines,
      suppressionBlocks: first.suppressionBlocks,
      protectedBlocks: first.protectedBlocks,
      totalLines: splitKeepEnds(text).length
    };
  }

  /* 统计：不修改内容，只数出待剥圆点（用于输入区实时提示） */
  function analyze(text) {
    var r = runOnce(text);
    return {
      dots: r.strippedLines.length,
      strippedLines: r.strippedLines,
      warnings: r.warnings,
      protectedBlocks: r.protectedBlocks,
      totalLines: splitKeepEnds(text).length,
      suppressionBlocks: r.suppressionBlocks
    };
  }

  return { strip: strip, analyze: analyze, splitKeepEnds: splitKeepEnds, version: '3.3.2' };
});
