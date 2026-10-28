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

7. How-to and archived short results for each host are under “Examples in other AI apps” below; full Muse / WorkBuddy limits: [`docs/宿主适配-Muse与WorkBuddy.md`](docs/宿主适配-Muse与WorkBuddy.md); eight-host index: [`docs/宿主外部实测索引.md`](docs/宿主外部实测索引.md).
8. For the scan-cost trade-off of banning bullets, and what this Skill does not cover downstream (Word / HTML), see [`docs/扫读代价与下游边界.md`](docs/扫读代价与下游边界.md).

### Examples in other AI apps

Each host below uses the same three fields: **How**, **Result**, **Limit**. Results are external archives (aligned to tip `90b40d16` / v3.2.0 context and filed at v3.3.1). Files on disk do not mean the skill is loaded or enforced, and this does not promise 100% on any host or model. This release does not claim a new round of algorithm or script testing. Pass line means: `--check` exit `0`, report `stripped=0`, and `summary.suppression_blocks == 0`.

**WorkBuddy.** How: install under user skills so the skill can appear in the list; for full-document persistence, copy the default-writing rules into custom instructions and run the pass line before delivery. Result: external archive — pass; may be treated as final. For the landed sample set—about 19k characters of thesis-style text, seven format-boundary cases, a Word bullet sample, and a list-heavy ops manual—the pass line held. Limit: files in a host directory do not force every reply to drop discs.

**Muse.** How: hand `skills/no-markdown-bullets/` into the chat with an explicit convention for a one-off trial; lasting use needs a Muse-local rewrite (`SKILL.md` without frontmatter plus `skill.yaml`) and the pass line from the repo root. Result: external archive — pass, no blocker; may be treated as final under those conditions; a thesis-style trial worked on the prompt path. Limit: convention plus post-check, not a global hard ban on bullets.

**Doubao.** How: hand the Skill directory into chat or into user skills; optionally copy the default-writing rules into custom instructions; run the pass line from the repo root before delivery. Result: external archive — usable, no blocker; may be treated as final (low friction, high availability). Limit: whether the skill list shows it does not gate use.

**ZCode.** How: hand the Skill directory into chat, or place it per `docs/install.md` (often under `~/.agents/skills/`); run the pass line before delivery. Result: external archive — may be treated as final. Limit: a contrast trial did not prove the Skill removed discs, because the baseline body had no unordered lists; the pass line only shows that turn’s body had no leftover UL.

**Qoder.** How: with no install slot, use “hand to the AI + pass line from the repo root”; Discovery is not a gate. Result: external archive — may be treated as final; the install slot was removed and this repo keeps only the verification summary. Limit: cold-start delay before the skill appears is a host-side behavior.

**Grok Bot.** How: place the Skill where the host can load it, or call it out / attach the directory for that turn; run the pass line on the finished draft. Result: external archive — suited to writing conventions and post-processing, not a global hard switch. Limit: integration is manual; this does not guarantee every reply is disc-free.

**Cursor.** How: copy into project `.cursor/skills/` or user `~/.cursor/skills/` (`.agents/skills/` also works), or hand the directory into chat / copy the default-writing rules; run the pass line from the repo root before delivery. Result: external archive — path-compatible, low install cost; still convention plus post-check. Limit: whether Discovery lists the skill remains unverified, and Discovery is not a usage gate; a path that accepts files does not mean the model obeys every time.

**GPT / ChatGPT.** How: hand the Skill directory or the convention into chat; if the host exposes a Skills entry, you may try installing there; the checker still runs the pass line separately from the repo root. Result: external archive — script and repo CI pass. Limit: independent host-side acceptance is incomplete; do not read this as platform-wide integration success or an unconditional guarantee.

See [`docs/宿主适配-Muse与WorkBuddy.md`](docs/宿主适配-Muse与WorkBuddy.md) for Muse / WorkBuddy detail, and [`docs/宿主外部实测索引.md`](docs/宿主外部实测索引.md) for the eight-host archive summaries.

License: MIT (`LICENSE`).
