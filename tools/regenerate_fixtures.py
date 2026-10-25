#!/usr/bin/env python3
"""Regenerate the golden fixtures used by the regression test.

Run this only when the reported behavior is intended to change, then review the
diff and explain it in the commit message. The fixtures exist so that a refactor
which silently alters which lines get reported fails loudly.

Usage:
    python tools/regenerate_fixtures.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER = REPO_ROOT / "no-markdown-bullets" / "scripts" / "check_markdown_bullets.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures"


def load_checker():
    spec = importlib.util.spec_from_file_location("fixture_checker", CHECKER)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import {CHECKER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    checker = load_checker()
    count = 0
    for source in sorted(FIXTURES.glob("*.md")):
        result = checker.scan_document(source.read_text(encoding="utf-8"))
        payload = {
            "findings": [
                {"line": f.line, "code": f.code, "message": f.message}
                for f in result.findings
            ],
            "suppressed_lines": result.suppressed_lines,
            "suppression_blocks": result.suppression_blocks,
        }
        target = source.with_suffix(".json")
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        count += 1
        print(f"wrote {target.relative_to(REPO_ROOT)}")
    print(f"{count} fixtures regenerated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
