import importlib.util
import io
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


if __name__ == "__main__":
    unittest.main()
