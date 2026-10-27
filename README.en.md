# no-markdown-bullets

A reusable agent skill that bans reader-facing Markdown unordered lists (the disc bullets many previews render), keeps ordered lists and tables, and ships a stdlib strip/check script. This repo is a standalone docs + skill delivery; it does not modify or depend on other plugin repos. Versioning follows tag **v3.2.0** and `CHANGELOG.md`.

## Problem

Models often emit unordered lists that start with `-` / `*` / `+` plus whitespace (including empty items and task lists). GitHub previews and many chat UIs render those as dots (commonly `list-style: disc`). Editing one draft or site CSS does not stop the next generation, chat, or Word paste. You need a copyable contract: what is banned, what stays, and when exceptions apply.

## Features

1. **Skill contract**: Package the rules into `skills/no-markdown-bullets/` (including `SKILL.md`) so you can hand the whole folder to an AI.
2. **Strip and check**: `scripts/strip_md_ul.py` rewrites existing UL markers; `--check` / `--report` define the pass line (exit code, `stripped`, suppression counts).
3. **Three scenes**: Change source structure on GitHub; give the skill to the AI in chat (optionally run the script); paste plain text or clear bullets in Word / WPS (see `docs/`).
4. **Non-promises**: Host auto-load and 100% model compliance are not guaranteed. Files on disk ≠ loaded ≠ obeyed. `check_docx_numbering.py`, `evals/`, and `python-docx` are optional satellites off the main verification path.

## Technology

1. **Runtime**: Python 3.10+ stdlib for the main script; CI matrix 3.10 and 3.12.
2. **Main path**: Skill + `scripts/strip_md_ul.py` + `fixtures/` / unit tests.
3. **Pass line (model body)**: `--check` exit `0`, report `stripped=0`, and `summary.suppression_blocks == 0` (or no `no-markdown-bullets:` suppression comments in the body). Human sources may still use suppression blocks.
4. **Integration**: See `INTEGRATION.md`; rule details in `docs/规则与边界.md`.

## Usage

1. Hand `skills/no-markdown-bullets/` to the target AI, or copy it into the host skills directory (common paths in `docs/install.md`); ask it to follow `SKILL.md`.
2. Optionally save the visible model body and check:

```bash
python scripts/strip_md_ul.py --check --report - output.md
```

3. Common rewrite commands (stdout by default; does not overwrite the source):

```bash
python scripts/strip_md_ul.py input.md
python scripts/strip_md_ul.py --dry-run input.md
python scripts/strip_md_ul.py --report report.json input.md
```

4. Repo self-test:

```bash
python -m unittest discover -s tests -v
```

Chinese primary README: [README.md](README.md).

## License

MIT; see `LICENSE`.
