# No Markdown Bullets (去黑点)

[简体中文](README.md)

A reusable agent skill that removes disc bullets rendered from reader-facing Markdown unordered lists, while keeping ordered lists and tables. This repo is a standalone docs + skill delivery; it does not modify or depend on other plugin repos. Versioning follows tags and `CHANGELOG.md`. The repo’s Chinese name is 去黑点; whether a host skill list shows Chinese depends on the host. Call-out still works with id `no-markdown-bullets`.

## Problem

Models often emit unordered lists that start with `-` / `*` / `+` plus whitespace (including empty items), plus task lists. GitHub previews and many chat UIs draw those as dots. `•` / `·` are ordinary characters, not list syntax. Editing one draft or site CSS does not stop the next generation, chat, or Word paste.

## Features

1. **Banned**: reader-facing unordered lists and task lists (task lists cannot be kept via a “keep bullets” exception).
2. **Kept**: ordered lists, tables, code blocks, thematic breaks, inline emphasis, and similar.
3. **Exception**: when the user clearly asks to keep bullets in that turn, ordinary UL may stay; task lists may not.
4. **Shape**: `skills/no-markdown-bullets/` (with `SKILL.md`) plus `scripts/strip_md_ul.py`. No prose polish, no browser/Word plug-in, no npm package. Host enforcement is **not** promised: files on disk ≠ loaded ≠ obeyed.

External field evidence aligned to tip `90b40d16` / v3.2.0 includes an ~19k-character thesis-style body, seven format-boundary suites, a hand-made Word bullet docx, and a list-heavy operations manual. From that tip through tip `302f888` / v3.3.0, `strip_md_ul.py` behavior was unchanged (v3.3.0 was a docs release); this release does not claim a new round of host field tests. This does **not** promise 100% on any host or model.

## Technology

1. Python 3.10+ stdlib runs the script; CI matrix is 3.10 and 3.12.
2. Main path is the Skill plus `strip_md_ul.py`; `check_docx_numbering.py` / `evals/` / `python-docx` are optional satellites.
3. Pass line for model body: `--check` exit `0`, report `stripped=0`, and `summary.suppression_blocks == 0`. Human sources may still use suppression blocks.
4. Rule details: `docs/规则与边界.md`; install paths: `docs/install.md`.

## Usage

1. **Recommended**: hand `skills/no-markdown-bullets/` to the target AI and ask it to follow `SKILL.md`. Host skill-list screenshots and Discovery are not a usage gate.
2. **Custom instructions (standing)**: copy the following “default writing” rules into the host custom instructions / system area (same meaning as `SKILL.md`; do not change the sense):

   When generating reader-facing Markdown, or body text that will be pasted into GitHub, chat, or Word:

   1. Write narration, explanation, and conclusions as ordinary paragraphs.
   2. Write steps, sequences, and items you need to cite one by one as numbered lists.
   3. Write field-aligned comparisons as tables. If the chat client has no tables, use a numbered list with each item as `field: value`.
   4. Split short items that have no order and need no numbering into separate paragraphs.

   Do not draft an unordered list and then swap markers. Replacing hyphens with asterisks or plus signs still yields an unordered list.

3. **Explicit call-out**: when the user names `no-markdown-bullets` in chat, read this repo’s `SKILL.md`, and from the repository root check the visible model body:

   ```bash
   python scripts/strip_md_ul.py --check --report - body.md
   ```

   Pass requires exit code `0`, report `stripped=0`, and `summary.suppression_blocks == 0`.

4. **Strong-list genre exception**: for product docs, meeting notes, and similar list-heavy genres, when the user clearly asks to keep bullets in that turn, ordinary unordered lists may stay; task lists may not.
5. Optionally copy into a host skills directory; common paths are in `docs/install.md`. Missing from a discovery list does not block use.
6. By default the script writes the rewrite to stdout and does not modify the source:

   ```bash
   python scripts/strip_md_ul.py input.md
   python scripts/strip_md_ul.py --dry-run input.md
   ```

7. Muse / WorkBuddy how-to and short results are under “Examples in other AI apps” below; full limits: [`docs/宿主适配-Muse与WorkBuddy.md`](docs/宿主适配-Muse与WorkBuddy.md).
8. For the scan-cost trade-off of banning bullets, and what this Skill does not cover downstream (Word / HTML), see [`docs/扫读代价与下游边界.md`](docs/扫读代价与下游边界.md).

### Examples in other AI apps

Short results from v3.2.0 materials already in-repo. Files on disk do not mean the skill is loaded or enforced, and this does not promise 100% on any host or model.

**Muse.** Hand `skills/no-markdown-bullets/` into the chat with an explicit convention for a one-off trial; lasting use needs a Muse-local rewrite (`SKILL.md` without frontmatter plus `skill.yaml`) and `--check` from the repo root. A thesis-style trial worked on the prompt path; Muse cannot hard-ban bullets globally.

**WorkBuddy.** Installing under user skills makes the skill listable; persistence needs the default-writing rules copied into custom instructions, plus the script pass line before delivery. For the landed sample set—about 19k characters of thesis-style text, seven format-boundary cases, a Word bullet sample, and a list-heavy ops manual—the pass line held (exit `0`, `stripped=0`, `suppression_blocks=0`).

See [`docs/宿主适配-Muse与WorkBuddy.md`](docs/宿主适配-Muse与WorkBuddy.md).

License: MIT (`LICENSE`).
