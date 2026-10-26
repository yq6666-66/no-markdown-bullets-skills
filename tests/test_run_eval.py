import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "evals" / "run_eval.py"
SPEC = importlib.util.spec_from_file_location("run_eval", SCRIPT)
EVAL = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = EVAL
SPEC.loader.exec_module(EVAL)

CHECKER = EVAL.load_stripper()


class AnalyseTests(unittest.TestCase):
    def analyse(self, text):
        return EVAL.analyse(text, CHECKER)

    def test_prose_only(self):
        result = self.analyse("A paragraph.\n\nAnother paragraph.\n")
        self.assertEqual(result.bullets, 0)
        self.assertEqual(result.ordered, 0)
        self.assertEqual(result.paragraphs, 2)

    def test_unordered_list_is_counted(self):
        result = self.analyse("- one\n- two\n")
        self.assertEqual(result.bullets, 2)
        self.assertEqual(result.paragraphs, 0)

    def test_ordered_list_is_counted_and_not_a_bullet(self):
        result = self.analyse("1. one\n2. two\n")
        self.assertEqual(result.bullets, 0)
        self.assertEqual(result.ordered, 2)

    def test_table_is_detected(self):
        text = "| A | B |\n| --- | --- |\n| 1 | 2 |\n"
        result = self.analyse(text)
        self.assertEqual(result.tables, 1)
        self.assertEqual(result.paragraphs, 0)

    def test_fenced_code_is_not_structure(self):
        text = "```markdown\n- not a bullet\n1. not ordered\n```\n"
        result = self.analyse(text)
        self.assertEqual(result.bullets, 0)
        self.assertEqual(result.ordered, 0)

    def test_quote_prefix_is_not_a_paragraph(self):
        result = self.analyse("> quoted\n")
        self.assertEqual(result.paragraphs, 0)

    def test_heading_is_not_a_paragraph(self):
        result = self.analyse("## Heading\n\nBody\n")
        self.assertEqual(result.paragraphs, 1)

    def test_longest_block_tracks_the_wall_of_text_risk(self):
        short = self.analyse("short one\n\nshort two\n")
        long = self.analyse("x" * 900 + "\n")
        self.assertLess(short.longest_block, long.longest_block)
        self.assertGreaterEqual(long.longest_block, 900)


class ExpectationTests(unittest.TestCase):
    def analysis(self, **kwargs):
        base = {
            "bullets": 0,
            "ordered": 0,
            "tables": 0,
            "paragraphs": 1,
            "chars": 100,
            "longest_block": 100,
        }
        base.update(kwargs)
        return EVAL.Analysis(**base)

    def test_prose_requires_no_lists(self):
        self.assertTrue(self.analysis().meets("prose"))
        self.assertFalse(self.analysis(bullets=1).meets("prose"))
        self.assertFalse(self.analysis(ordered=3).meets("prose"))

    def test_ordered_requires_two_items(self):
        self.assertTrue(self.analysis(ordered=2).meets("ordered"))
        self.assertFalse(self.analysis(ordered=1).meets("ordered"))

    def test_table_or_ordered_accepts_either(self):
        self.assertTrue(self.analysis(tables=1).meets("table_or_ordered"))
        self.assertTrue(self.analysis(ordered=4).meets("table_or_ordered"))
        self.assertFalse(self.analysis(bullets=3).meets("table_or_ordered"))

    def test_ordered_or_prose_rejects_bullets(self):
        self.assertTrue(self.analysis(ordered=3).meets("ordered_or_prose"))
        self.assertTrue(self.analysis().meets("ordered_or_prose"))
        self.assertFalse(
            self.analysis(bullets=2, paragraphs=0).meets("ordered_or_prose")
        )

    def test_unknown_expectation_is_an_error(self):
        with self.assertRaises(ValueError):
            self.analysis().meets("whatever")


class PromptLoadingTests(unittest.TestCase):
    def test_shipped_prompt_set_has_eight_entries(self):
        prompts = EVAL.load_prompts(EVAL.PROMPTS_PATH)
        self.assertEqual(len(prompts), 8)
        self.assertEqual(len({prompt.id for prompt in prompts}), 8)

    def test_every_prompt_declares_a_known_expectation(self):
        for prompt in EVAL.load_prompts(EVAL.PROMPTS_PATH):
            with self.subTest(prompt=prompt.id):
                self.assertIn(
                    prompt.expect,
                    {"prose", "ordered", "table", "table_or_ordered",
                     "ordered_or_prose"},
                )

    def test_duplicate_id_is_rejected(self):
        payload = {
            "prompts": [
                {"id": "a", "text": "x", "expect": "prose"},
                {"id": "a", "text": "y", "expect": "prose"},
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(SystemExit):
                EVAL.load_prompts(path)

    def test_empty_prompt_list_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p.json"
            path.write_text('{"prompts": []}', encoding="utf-8")
            with self.assertRaises(SystemExit):
                EVAL.load_prompts(path)

    def test_missing_field_is_rejected(self):
        payload = {"prompts": [{"id": "a", "expect": "prose"}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(SystemExit):
                EVAL.load_prompts(path)


class SampleModeTests(unittest.TestCase):
    def write_prompts(self, directory):
        payload = {
            "prompts": [
                {"id": "a", "text": "one", "expect": "prose"},
                {"id": "b", "text": "two", "expect": "ordered"},
            ]
        }
        path = Path(directory) / "prompts.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_condition_subdirectory_wins_over_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompts = self.write_prompts(directory)
            (root / "samples" / "with-skill").mkdir(parents=True)
            (root / "samples" / "with-skill" / "a.md").write_text(
                "prose answer\n", encoding="utf-8"
            )
            (root / "samples" / "a.md").write_text("- root answer\n", encoding="utf-8")
            out = root / "result.json"
            status = EVAL.run(
                samples=root / "samples",
                condition="with-skill",
                command=None,
                timeout=10,
                out=out,
                prompts_path=prompts,
                stdout=io.StringIO(),
                stderr=io.StringIO(),
            )
            self.assertEqual(status, EVAL.EXIT_OK)
            document = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(document["summary"]["outputs"], 1)
            self.assertEqual(document["summary"]["bullet_outputs"], 0)

    def test_missing_samples_are_skipped_with_a_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompts = self.write_prompts(directory)
            (root / "samples").mkdir()
            (root / "samples" / "a.md").write_text("answer\n", encoding="utf-8")
            stderr = io.StringIO()
            status = EVAL.run(
                samples=root / "samples",
                condition="only-a",
                command=None,
                timeout=10,
                out=None,
                prompts_path=prompts,
                stdout=io.StringIO(),
                stderr=stderr,
            )
            self.assertEqual(status, EVAL.EXIT_OK)
            self.assertIn("no sample for 'b'", stderr.getvalue())


class CommandModeTests(unittest.TestCase):
    def test_command_provider_is_wired_through_stdin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = {"prompts": [{"id": "a", "text": "PROMPT-TOKEN",
                                     "expect": "ordered"}]}
            prompts = root / "prompts.json"
            prompts.write_text(json.dumps(payload), encoding="utf-8")
            # Echo the prompt back, prefixed so it becomes an ordered list.
            command = (
                f'"{sys.executable}" -c "'
                "import sys;t=sys.stdin.read().strip();"
                "print('1. ' + t);print('2. again')\""
            )
            out = root / "r.json"
            status = EVAL.run(
                samples=None,
                condition="echo",
                command=command,
                timeout=30,
                out=out,
                prompts_path=prompts,
                stdout=io.StringIO(),
                stderr=io.StringIO(),
            )
            self.assertEqual(status, EVAL.EXIT_OK)
            document = json.loads(out.read_text(encoding="utf-8"))
            row = document["prompts"][0]
            self.assertEqual(row["ordered"], 2)
            self.assertTrue(row["expectation_met"])

    def test_failing_command_reports_the_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = {"prompts": [{"id": "a", "text": "x", "expect": "prose"}]}
            prompts = root / "prompts.json"
            prompts.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(SystemExit):
                EVAL.run(
                    samples=None,
                    condition="boom",
                    command=f'"{sys.executable}" -c "import sys;sys.exit(3)"',
                    timeout=30,
                    out=None,
                    prompts_path=prompts,
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )


class CompareTests(unittest.TestCase):
    def write_result(self, path, condition, rows):
        result = EVAL.RunResult(
            condition=condition,
            rows=[EVAL._row_from_dict(row, "test") for row in rows],
            stripper_version="test",
            generated_at="2026-01-01T00:00:00+00:00",
        )
        path.write_text(
            json.dumps(result.as_dict(), ensure_ascii=False), encoding="utf-8"
        )
        return path

    def test_compare_reports_delta_in_the_intended_direction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = self.write_result(
                root / "a.json",
                "baseline",
                [
                    {"id": "p1", "expect": "prose", "bullets": 2, "ordered": 0,
                     "tables": 0, "paragraphs": 0, "chars": 10, "longest_block": 5,
                     "expectation_met": False},
                ],
            )
            after = self.write_result(
                root / "b.json",
                "with-skill",
                [
                    {"id": "p1", "expect": "prose", "bullets": 0, "ordered": 0,
                     "tables": 0, "paragraphs": 1, "chars": 12, "longest_block": 12,
                     "expectation_met": True},
                ],
            )
            output = io.StringIO()
            status = EVAL.compare(baseline, after, output)
            self.assertEqual(status, EVAL.EXIT_OK)
            text = output.getvalue()
            self.assertIn("bullet_rate delta", text)
            self.assertIn("-1.0", text)
            self.assertIn("does not by itself", text)


if __name__ == "__main__":
    unittest.main()
