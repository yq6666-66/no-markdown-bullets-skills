import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "no-markdown-bullets"
    / "scripts"
    / "check_markdown_bullets.py"
)
SPEC = importlib.util.spec_from_file_location("check_markdown_bullets", SCRIPT)
CHECKER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = CHECKER
SPEC.loader.exec_module(CHECKER)


class ScanTextTests(unittest.TestCase):
    def lines(self, text):
        return [finding.line for finding in CHECKER.scan_text(text)]

    def test_detects_all_unordered_markers(self):
        self.assertEqual(self.lines("- one\n* two\n+ three\n"), [1, 2, 3])

    def test_detects_tasks_nested_lists_and_blockquotes(self):
        text = "- [ ] task\n1. ordered\n   - nested\n> * quoted\n"
        self.assertEqual(self.lines(text), [1, 3, 4])

    def test_preserves_ordered_lists(self):
        self.assertEqual(self.lines("1. one\n2) two\n123456789. three\n"), [])

    def test_preserves_tables(self):
        text = "| A | B |\n| --- | :---: |\n| 1 | 2 |\n"
        self.assertEqual(self.lines(text), [])

    def test_preserves_thematic_breaks_and_emphasis(self):
        text = "---\n- - -\n***\n* * *\n+ + +\n*emphasis*\n"
        self.assertEqual(self.lines(text), [])

    def test_preserves_escaped_and_inline_markers(self):
        self.assertEqual(self.lines("\\- literal\ntext - not a list\n"), [])

    def test_ignores_fenced_code(self):
        text = "```markdown\n- code\n```\n~~~\n* code\n~~~\n- real\n"
        self.assertEqual(self.lines(text), [7])

    def test_ignores_fenced_code_in_ordered_list(self):
        text = "1. item\n    ```markdown\n    - code\n    ```\n2. next\n"
        self.assertEqual(self.lines(text), [])

    def test_ignores_indented_code(self):
        self.assertEqual(self.lines("    - code\n\t* code\n"), [])

    def test_detects_nested_list_after_ordered_item(self):
        self.assertEqual(self.lines("1. item\n    - nested\n"), [2])

    def test_empty_unordered_item_is_detected(self):
        self.assertEqual(self.lines("-\n*\n+\n"), [1, 2, 3])

    def test_list_like_text_after_paragraph_is_detected(self):
        self.assertEqual(self.lines("paragraph\n- item\n"), [2])

    def test_quote_marker_inside_fence_is_code(self):
        text = "```markdown\n> - quoted example\n```\n"
        self.assertEqual(self.lines(text), [])

    def test_fence_inside_blockquote(self):
        text = "> ```markdown\n> - code\n> ```\n> - after\n"
        self.assertEqual(self.lines(text), [4])

    def test_ending_blockquote_ends_its_fence(self):
        text = "> ```markdown\n> - code\n\n- real\n"
        self.assertEqual(self.lines(text), [4])

    def test_closed_frontmatter_is_skipped(self):
        text = "---\ntitle: doc\ntags:\n  - alpha\n  - beta\n---\n\n- real\n"
        self.assertEqual(self.lines(text), [8])

    def test_toml_frontmatter_is_skipped(self):
        text = "+++\ntags = [\"a\"]\n+++\n\n- real\n"
        self.assertEqual(self.lines(text), [5])

    def test_unclosed_frontmatter_still_reports(self):
        text = "---\ntags:\n  - alpha\n\n- real\n"
        self.assertEqual(self.lines(text), [3, 5])

    def test_frontmatter_with_blank_line_is_not_skipped(self):
        text = "---\ntitle: doc\n\n- body\n---\n"
        self.assertEqual(self.lines(text), [4])

    def test_thematic_break_is_not_frontmatter(self):
        text = "---\n\nparagraph\n\n---\n\n- real\n"
        self.assertEqual(self.lines(text), [7])

    def test_suppression_region_hides_findings(self):
        text = (
            "<!-- no-markdown-bullets: off reason=\"legacy template\" -->\n"
            "- hidden\n"
            "<!-- no-markdown-bullets: on reason=\"resume\" -->\n"
            "- visible\n"
        )
        self.assertEqual(self.lines(text), [4])

    def test_suppression_requires_reason(self):
        text = "<!-- no-markdown-bullets: off -->\n- still checked\n"
        self.assertEqual(self.lines(text), [2])

    def test_empty_reason_is_rejected(self):
        text = "<!-- no-markdown-bullets: off reason=\"   \" -->\n- checked\n"
        self.assertEqual(self.lines(text), [2])

    def test_unclosed_suppression_is_reported(self):
        text = "<!-- no-markdown-bullets: off reason=\"x\" -->\n- hidden\n"
        findings = CHECKER.scan_text(text)
        self.assertEqual(
            [(f.line, f.code) for f in findings], [(1, "unclosed-suppression")]
        )

    def test_suppression_inside_code_block_is_inert(self):
        text = (
            "```markdown\n"
            "<!-- no-markdown-bullets: off reason=\"x\" -->\n"
            "```\n"
            "- real\n"
        )
        self.assertEqual(self.lines(text), [4])

    def test_suppression_counts_and_blocks(self):
        text = (
            "<!-- no-markdown-bullets: off reason=\"a\" -->\n"
            "- hidden\n"
            "text\n"
            "<!-- no-markdown-bullets: on reason=\"b\" -->\n"
        )
        result = CHECKER.scan_document(text)
        self.assertEqual(result.suppression_blocks, 1)
        self.assertEqual(result.suppressed_lines, 2)
        self.assertEqual(result.findings, [])

    def test_single_quoted_reason_is_accepted(self):
        text = (
            "<!-- no-markdown-bullets: off reason='legacy' -->\n"
            "- hidden\n"
            "<!-- no-markdown-bullets: on reason='done' -->\n"
            "- visible\n"
        )
        self.assertEqual(self.lines(text), [4])

    def test_indented_directive_is_honoured(self):
        text = (
            "   <!-- no-markdown-bullets: off reason=\"x\" -->\n"
            "- hidden\n"
            "<!-- no-markdown-bullets: on reason=\"y\" -->\n"
            "- visible\n"
        )
        self.assertEqual(self.lines(text), [4])

    def test_angle_bracket_in_text_is_not_a_quote(self):
        self.assertEqual(self.lines("a > b\n- c\n"), [2])

    def test_quote_without_space_still_counts(self):
        self.assertEqual(self.lines(">- quoted\n"), [1])

    def test_marker_without_following_space_is_not_a_list(self):
        self.assertEqual(self.lines("-foo\n*bar\n+baz\n"), [])

    def test_overlong_digit_run_does_not_swallow_next_bullet(self):
        self.assertEqual(self.lines("1234567890. text\n- item\n"), [2])

    def test_deeply_nested_blockquote(self):
        self.assertEqual(self.lines("> > > - deep\n"), [1])

    def test_four_backtick_fence_keeps_three_backtick_line(self):
        text = "````markdown\n```\n- code\n````\n- real\n"
        self.assertEqual(self.lines(text), [5])

    def test_tilde_fence_ignores_backticks(self):
        text = "~~~\n```\n- code\n~~~\n- real\n"
        self.assertEqual(self.lines(text), [5])

    def test_blockquote_lists_do_not_leak_into_next_blockquote(self):
        text = "> 1. item\n>    - nested\n\n> - second\n"
        self.assertEqual(self.lines(text), [2, 4])


class CommandTests(unittest.TestCase):
    def test_good_bad_and_override_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good = root / "good.md"
            bad = root / "bad.md"
            good.write_text("1. fine\n", encoding="utf-8")
            bad.write_text("- bad\n", encoding="utf-8")

            self.assertEqual(CHECKER.run([str(good)], stdout=io.StringIO()), 0)
            output = io.StringIO()
            self.assertEqual(CHECKER.run([str(bad)], stdout=output), 1)
            self.assertIn("bad.md:1:", output.getvalue())
            self.assertEqual(
                CHECKER.run([str(bad)], allow=True, stdout=io.StringIO()), 0
            )

    def test_allow_rejects_multiple_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "a.md"
            second = root / "b.md"
            first.write_text("- a\n", encoding="utf-8")
            second.write_text("- b\n", encoding="utf-8")
            stderr = io.StringIO()
            status = CHECKER.run(
                [str(first), str(second)],
                allow=True,
                stdout=io.StringIO(),
                stderr=stderr,
            )
            self.assertEqual(status, 2)
            self.assertIn("--allow accepts a single path", stderr.getvalue())

    def test_text_output_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "x.md"
            bad.write_text("- one\n", encoding="utf-8")
            output = io.StringIO()
            CHECKER.run([str(bad)], stdout=output)
            self.assertEqual(
                output.getvalue(),
                f"{bad}:1: Markdown unordered list marker '-'\n",
            )

    def test_json_output_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "x.md"
            bad.write_text(
                "<!-- no-markdown-bullets: off reason=\"r\" -->\n"
                "hidden\n"
                "<!-- no-markdown-bullets: on reason=\"r\" -->\n"
                "* hit\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            status = CHECKER.run(
                [str(bad)], output_format="json", stdout=output
            )
            self.assertEqual(status, 1)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["version"], CHECKER.__version__)
            self.assertEqual(payload["summary"]["findings"], 1)
            self.assertEqual(payload["summary"]["suppressed_lines"], 1)
            self.assertEqual(len(payload["files"]), 1)
            finding = payload["files"][0]["findings"][0]
            self.assertEqual(finding["code"], "unordered-list")
            self.assertEqual(finding["line"], 4)

    def test_json_output_passes_when_clean(self):
        with tempfile.TemporaryDirectory() as directory:
            good = Path(directory) / "g.md"
            good.write_text("1. ok\n", encoding="utf-8")
            output = io.StringIO()
            status = CHECKER.run([str(good)], output_format="json", stdout=output)
            self.assertEqual(status, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["summary"], {
                "files": 1,
                "findings": 0,
                "suppressed_lines": 0,
                "suppression_ratio": 0.0,
            })

    def test_directory_only_reads_markdown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "note.txt").write_text("- text\n", encoding="utf-8")
            (root / "note.md").write_text("1. markdown\n", encoding="utf-8")
            self.assertEqual(CHECKER.run([str(root)], stdout=io.StringIO()), 0)


    def test_stdin(self):
        output = io.StringIO()
        status = CHECKER.run(["-"], stdin=io.StringIO("* bad\n"), stdout=output)
        self.assertEqual(status, 1)
        self.assertIn("<stdin>:1:", output.getvalue())

    def test_missing_path_is_an_error(self):
        self.assertEqual(
            CHECKER.run(
                ["definitely-missing.md"], stdout=io.StringIO(), stderr=io.StringIO()
            ),
            2,
        )


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "no-markdown-bullets"


class WalkTests(unittest.TestCase):
    """Lock down which files a directory scan sees."""

    def walk(self, root):
        return [path.name for path in CHECKER._iter_markdown_files(root)]

    def test_ignored_directories_are_pruned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "notes").mkdir()
            (root / "notes" / "keep.md").write_text("1. x\n", encoding="utf-8")
            for ignored in ("node_modules", ".venv", "__pycache__", ".git"):
                folder = root / ignored
                folder.mkdir()
                (folder / "skip.md").write_text("- x\n", encoding="utf-8")
            self.assertEqual(self.walk(root), ["keep.md"])

    def test_explicitly_passing_an_ignored_directory_yields_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "node_modules"
            folder.mkdir()
            (folder / "skip.md").write_text("- x\n", encoding="utf-8")
            self.assertEqual(self.walk(folder), [])

    def test_suffix_match_is_case_insensitive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "UPPER.MD").write_text("1. x\n", encoding="utf-8")
            (root / "lower.md").write_text("1. x\n", encoding="utf-8")
            (root / "notes.txt").write_text("- x\n", encoding="utf-8")
            # Sort order differs between platforms, the membership does not.
            self.assertEqual(sorted(self.walk(root)), ["UPPER.MD", "lower.md"])

    def test_nested_files_are_found_in_stable_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for depth in range(3):
                folder = root.joinpath(*[f"level{index}" for index in range(depth + 1)])
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f"doc{depth}.md").write_text("1. x\n", encoding="utf-8")
            first = [str(path) for path in CHECKER._iter_markdown_files(root)]
            second = [str(path) for path in CHECKER._iter_markdown_files(root)]
            self.assertEqual(first, second)
            self.assertEqual(len(first), 3)


class RepositoryConsistencyTests(unittest.TestCase):
    """Keep the shipped docs compliant with the rule they describe."""

    def test_repository_docs_pass_their_own_check(self):
        targets = [
            REPO_ROOT / "README.md",
            REPO_ROOT / "CHANGELOG.md",
            REPO_ROOT / "docs" / "design.md",
            SKILL_DIR / "SKILL.md",
            SKILL_DIR / "references" / "scenarios.md",
        ]
        for target in targets:
            with self.subTest(target=target.name):
                output = io.StringIO()
                self.assertEqual(
                    CHECKER.run([str(target)], stdout=output),
                    0,
                    output.getvalue(),
                )

    def test_good_example_passes(self):
        target = SKILL_DIR / "examples" / "good.md"
        self.assertEqual(CHECKER.run([str(target)], stdout=io.StringIO()), 0)

    def test_bad_example_reports_six_findings(self):
        output = io.StringIO()
        self.assertEqual(
            CHECKER.run([str(SKILL_DIR / "examples" / "bad.md")], stdout=output), 1
        )
        self.assertEqual(len(output.getvalue().strip().splitlines()), 6)

    def test_suppression_example_passes_end_to_end(self):
        target = SKILL_DIR / "examples" / "suppression.md"
        output = io.StringIO()
        status = CHECKER.run([str(target)], stdout=output)
        self.assertEqual(status, 0, output.getvalue())
        result = CHECKER.scan_document(target.read_text(encoding="utf-8-sig"))
        self.assertEqual(result.suppression_blocks, 1)
        self.assertEqual(result.suppressed_lines, 2)

    def test_skill_frontmatter_names_the_skill(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8-sig")
        self.assertTrue(text.startswith("---\nname: no-markdown-bullets\n"))

    def test_documented_suppression_markers_match_the_implementation(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8-sig")
        self.assertIn(CHECKER.SUPPRESSION_OFF, text)
        self.assertIn(CHECKER.SUPPRESSION_ON, text)


if __name__ == "__main__":
    unittest.main()
