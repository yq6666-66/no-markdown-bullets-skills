"""fixtures、退出码、CLI 与仓库文案的验收测试。"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "strip_md_ul.py"
SPEC = importlib.util.spec_from_file_location("strip_md_ul", SCRIPT)
strip_md_ul = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = strip_md_ul
SPEC.loader.exec_module(strip_md_ul)

DOC_PATHS = [
    ROOT / "README.md",
    ROOT / "INTEGRATION.md",
    ROOT / "fixtures" / "README.md",
    ROOT / "skills" / "no-markdown-bullets" / "SKILL.md",
    *sorted((ROOT / "docs").glob("*.md")),
]


def fixture_cases():
    cases = []
    for meta_path in sorted((ROOT / "fixtures").glob("*/meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        folder = meta_path.parent
        cases.append(
            {
                "name": folder.name,
                "meta": meta,
                "input": (folder / "input.md").read_bytes(),
                "expected": (folder / "expected.md").read_bytes(),
            }
        )
    return cases


class FixtureTests(unittest.TestCase):
    def test_fixture_set_covers_required_boundaries(self):
        names = {case["name"] for case in fixture_cases()}
        required = {
            "01_leading_ul",
            "02_ordered",
            "03_blockquote_ul",
            "04_nested",
            "05_task_list",
            "06_empty_item",
            "07_fence_backtick",
            "08_fence_tilde",
            "09_fence_unclosed",
            "10_fence_in_blockquote",
            "11_fence_in_list",
            "12_thematic",
            "13_yaml_front_matter",
            "15_table",
            "16_emphasis",
            "17_indented_code",
            "18_list_continuation",
            "19_blank_interrupts",
            "21_new_heading",
            "22_residual_ul",
            "23_crlf",
            "24_tab_after_marker",
            "25_no_final_newline",
            "29_json_fence",
        }
        self.assertTrue(required <= names)

    def test_each_fixture_has_input_expected_and_skip_reason(self):
        cases = fixture_cases()
        self.assertGreaterEqual(len(cases), 41)
        for case in cases:
            with self.subTest(case=case["name"]):
                meta = case["meta"]
                self.assertIn("description", meta)
                self.assertIsInstance(meta["expect_exit"], int)
                self.assertIn(meta["expect_exit"], (0, 1, 2))
                self.assertIsInstance(meta["skip_reason"], str)
                self.assertTrue(meta["skip_reason"].strip())
                self.assertTrue(case["input"] or case["name"])
                self.assertIn("expected", case)

    def test_strip_matches_expected_bytes_and_exit(self):
        for case in fixture_cases():
            with self.subTest(case=case["name"]):
                text = case["input"].decode("utf-8")
                result = strip_md_ul.strip_text(text)
                self.assertEqual(result.exit_code, case["meta"]["expect_exit"])
                self.assertEqual(result.text.encode("utf-8"), case["expected"])

    def test_success_and_skip_results_are_idempotent(self):
        for case in fixture_cases():
            if case["meta"]["expect_exit"] == 1:
                continue
            with self.subTest(case=case["name"]):
                first = strip_md_ul.strip_text(case["input"].decode("utf-8"))
                second = strip_md_ul.strip_text(first.text)
                self.assertEqual(second.text, first.text)
                self.assertEqual(second.exit_code, first.exit_code)

    def test_crlf_and_missing_newline_bytes_stay_on_disk(self):
        crlf = (ROOT / "fixtures" / "23_crlf" / "input.md").read_bytes()
        self.assertIn(b"\r\n", crlf)
        self.assertNotIn(b"\n", crlf.replace(b"\r\n", b""))
        bare = (ROOT / "fixtures" / "25_no_final_newline" / "input.md").read_bytes()
        self.assertFalse(bare.endswith(b"\n"))
        self.assertFalse(bare.endswith(b"\r"))


class CommandTests(unittest.TestCase):
    def test_stdout_does_not_overwrite_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "note.md"
            path.write_bytes("- keep-source\n".encode("utf-8"))
            before = path.read_bytes()
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, b"keep-source\n")
            self.assertEqual(path.read_bytes(), before)
            self.assertIn(b"info: stripped=1", proc.stderr)

    def test_check_suppresses_body_and_keeps_exit_code(self):
        source = ROOT / "fixtures" / "01_leading_ul" / "input.md"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--check", str(source)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, b"")
        self.assertIn(b"info: stripped=3", proc.stderr)

    def test_dry_run_matches_default_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "note.md"
            path.write_text("- item\n", encoding="utf-8")
            default = subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            dry = subprocess.run(
                [sys.executable, str(SCRIPT), "--dry-run", str(path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(default.returncode, 0)
            self.assertEqual(dry.returncode, 0)
            self.assertEqual(dry.stdout, default.stdout)
            self.assertIn(b"info: dry-run source-not-modified", dry.stderr)
            self.assertEqual(path.read_text(encoding="utf-8"), "- item\n")

    def test_residual_exit_and_unclosed_fence_exit(self):
        residual = ROOT / "fixtures" / "22_residual_ul"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(residual / "input.md")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, (residual / "expected.md").read_bytes())
        self.assertIn(b"residual unordered list", proc.stderr)

        unclosed = ROOT / "fixtures" / "09_fence_unclosed" / "input.md"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--check", str(unclosed)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        self.assertIn(b"unclosed fence", proc.stderr)

    def test_cli_preserves_crlf_bytes(self):
        folder = ROOT / "fixtures" / "23_crlf"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(folder / "input.md")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, (folder / "expected.md").read_bytes())

    def test_stdin_and_dash(self):
        for args in ([str(SCRIPT)], [str(SCRIPT), "-"]):
            with self.subTest(args=args):
                proc = subprocess.run(
                    [sys.executable, *args],
                    input=b"* item\n",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(proc.stdout, b"item\n")

    def test_usage_and_io_errors_exit_1(self):
        missing = subprocess.run(
            [sys.executable, str(SCRIPT), "missing-file.md"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(missing.returncode, 1)
        self.assertIn(b"not a file", missing.stderr)

        both = subprocess.run(
            [sys.executable, str(SCRIPT), "--check", "--dry-run"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(both.returncode, 1)

        unknown = subprocess.run(
            [sys.executable, str(SCRIPT), "--no-such-flag"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(unknown.returncode, 1)

        with tempfile.TemporaryDirectory() as directory:
            directory_arg = subprocess.run(
                [sys.executable, str(SCRIPT), directory],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(directory_arg.returncode, 1)

    def test_report_file_keeps_stdout_as_body(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "note.md"
            report_path = Path(directory) / "report.json"
            source.write_text("- item\n", encoding="utf-8", newline="\n")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--report",
                    str(report_path),
                    str(source),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, b"item\n")
            self.assertNotIn(b"{", proc.stdout)
            self.assertIn(b"info: stripped=1", proc.stderr)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["tool"], "strip_md_ul")
            self.assertEqual(payload["exit_code"], 0)
            self.assertEqual(payload["stripped_lines"], [1])
            self.assertNotIn("text", payload)
            self.assertTrue(
                any(item["code"] == "stripped" and item["exit_class"] == 0
                    for item in payload["findings"])
            )

    def test_report_dash_is_stderr_json_only(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--check", "--report", "-"],
            input='<!-- no-markdown-bullets: off reason="x" -->\n- hidden\n'.encode(
                "utf-8"
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        payload = json.loads(proc.stderr.decode("utf-8"))
        self.assertEqual(payload["exit_code"], 2)
        self.assertEqual(payload["source"], "<stdin>")
        codes = {item["code"]: item["exit_class"] for item in payload["findings"]}
        self.assertEqual(codes["unclosed-suppression"], 2)
        self.assertNotIn(b"info: stripped=", proc.stderr.splitlines()[0])

    def test_report_failure_does_not_emit_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            blocked = Path(directory) / "blocked"
            blocked.mkdir()
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--report", str(blocked)],
                input=b"- item\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(proc.stdout, b"")
            self.assertIn(b"error:", proc.stderr)

    def test_version_flag_prints_version_and_exits_zero(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        stdout = proc.stdout.replace(b"\r\n", b"\n").decode("utf-8")
        expected = f"strip_md_ul.py {strip_md_ul.__version__}\n"
        self.assertEqual(stdout, expected)
        self.assertEqual(proc.stderr, b"")
        help_proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(help_proc.returncode, 0)
        self.assertIn(b"--version", help_proc.stdout)


class RegionTests(unittest.TestCase):
    def test_four_space_directive_does_not_open_suppression(self):
        text = '    <!-- no-markdown-bullets: off reason="x" -->\n- hidden\n'
        result = strip_md_ul.strip_text(text)
        self.assertEqual(result.suppression_blocks, 0)
        self.assertEqual(result.regions, [])
        self.assertEqual(result.stripped_lines, [2])
        self.assertEqual(result.exit_code, 0)
        self.assertNotIn("- hidden", result.text)

        tabbed = strip_md_ul.strip_text(
            '\t<!-- no-markdown-bullets: off reason="x" -->\n- hidden\n'
        )
        self.assertEqual(tabbed.suppression_blocks, 0)
        self.assertEqual(tabbed.exit_code, 0)
        self.assertIsNone(
            strip_md_ul.match_directive(
                '    <!-- no-markdown-bullets: off reason="x" -->'
            )
        )
        self.assertIsNone(
            strip_md_ul.match_directive(
                '\t<!-- no-markdown-bullets: off reason="x" -->'
            )
        )
        self.assertIsNotNone(
            strip_md_ul.match_directive(
                '   <!-- no-markdown-bullets: off reason="x" -->'
            )
        )

    def test_front_matter_and_suppression_share_region_marker(self):
        text = (
            "---\n"
            "title: x\n"
            "---\n"
            '<!-- no-markdown-bullets: off reason="keep" -->\n'
            "- kept\n"
            '<!-- no-markdown-bullets: on reason="done" -->\n'
            "- gone\n"
        )
        result = strip_md_ul.strip_text(text)
        self.assertEqual(
            [region["kind"] for region in result.regions],
            ["frontmatter", "suppression"],
        )
        self.assertTrue(all(region["closed"] for region in result.regions))
        self.assertEqual(result.suppression_blocks, 1)
        self.assertEqual(result.suppressed_lines, 1)
        self.assertIn("- kept", result.text)
        self.assertTrue(result.text.endswith("gone\n"))
        self.assertEqual(result.exit_code, 0)

    def test_report_exit_classes_follow_process_exit(self):
        unclosed = strip_md_ul.strip_text(
            '<!-- no-markdown-bullets: off reason="x" -->\n- hidden\n'
        )
        report = strip_md_ul.build_report(unclosed, "<memory>")
        self.assertEqual(report["exit_code"], 2)
        self.assertNotIn("text", report)
        self.assertEqual(
            {item["code"] for item in report["findings"]},
            {"unclosed-suppression"},
        )

        residual = strip_md_ul.strip_text("- - still\n")
        residual_report = strip_md_ul.build_report(residual, "<memory>")
        self.assertEqual(residual_report["exit_code"], 1)
        self.assertTrue(
            any(
                item["code"] == "residual-unordered-list" and item["exit_class"] == 1
                for item in residual_report["findings"]
            )
        )

    def test_ported_b_hit_lines_are_the_stripped_lines(self):
        expected = {
            "59_b_fences": [12, 22],
            "60_b_frontmatter": [13, 19],
            "61_b_nesting": [4, 5, 9, 11, 19, 23, 24, 29],
            "62_b_structure": [33, 34, 35],
            "63_b_suppression": [8, 11, 14],
        }
        for name, lines in expected.items():
            with self.subTest(case=name):
                text = (ROOT / "fixtures" / name / "input.md").read_text(encoding="utf-8")
                result = strip_md_ul.strip_text(text)
                self.assertEqual(result.stripped_lines, lines)


class PlusOnlyLineTests(unittest.TestCase):
    def _run(self, text: str, check: bool = False) -> subprocess.CompletedProcess[bytes]:
        args = [sys.executable, str(SCRIPT)]
        if check:
            args.append("--check")
        return subprocess.run(
            args,
            input=text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_markers_do_not_treat_plus_as_thematic(self):
        self.assertNotIn("+", strip_md_ul.THEMATIC_MARKERS)
        self.assertTrue(set("-*_") <= set(strip_md_ul.THEMATIC_MARKERS))
        self.assertIn("+", strip_md_ul.UL_MARKERS)

    def test_bare_plus_run_becomes_empty_line_exit_0(self):
        proc = self._run("+ + +\n")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, b"\n")
        self.assertNotIn(b"residual unordered list", proc.stderr)

        checked = self._run("+ + +\n", check=True)
        self.assertEqual(checked.returncode, 0)
        self.assertEqual(checked.stdout, b"")
        self.assertNotIn(b"residual unordered list", checked.stderr)

    def test_fenced_plus_run_is_unchanged_exit_0(self):
        for source in ("```\n+ + +\n```\n", "~~~\n+ + +\n~~~\n"):
            with self.subTest(source=source):
                proc = self._run(source)
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(proc.stdout, source.encode("utf-8"))
                self.assertNotIn(b"residual unordered list", proc.stderr)

    def test_plus_item_still_strips_exit_0(self):
        proc = self._run("+ item\n")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, b"item\n")

    def test_hyphen_and_star_thematic_breaks_stay_exit_0(self):
        for source in ("- - -\n", "***\n", "* * *\n", "___\n"):
            with self.subTest(source=source):
                proc = self._run(source)
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(proc.stdout, source.encode("utf-8"))

    def test_blockquote_tabs_trailing_space_and_four_pluses_become_empty(self):
        cases = (
            "> + + +\n",
            "> > + + +\n",
            "+\t+\t+\n",
            "+ + +\t\n",
            "+ + +   \n",
            "+ + + +\n",
            "+++\n",
            "   + + +\n",
        )
        for source in cases:
            with self.subTest(source=source):
                proc = self._run(source)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(proc.stdout, b"\n")
                self.assertNotIn(b"residual unordered list", proc.stderr)

    def test_exactly_two_pluses_stay_on_ul_residual_path(self):
        proc = self._run("+ +\n")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, b"+\n")
        self.assertNotEqual(proc.stdout, b"\n")
        self.assertIn(b"residual unordered list", proc.stderr)

    def test_mixed_plus_item_and_plus_run_with_real_thematic_breaks(self):
        proc = self._run("+ item\n+ + +\n- - -\n***\n")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, b"item\n\n- - -\n***\n")
        self.assertNotIn(b"residual unordered list", proc.stderr)

    def test_indented_plus_run_stays_indented_code(self):
        for source in ("    + + +\n", "\t+ + +\n"):
            with self.subTest(source=source):
                proc = self._run(source)
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(proc.stdout, source.encode("utf-8"))


class RepoTextTests(unittest.TestCase):
    def test_delivered_docs_have_no_strippable_ul(self):
        for path in DOC_PATHS:
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                result = strip_md_ul.strip_text(path.read_text(encoding="utf-8"))
                self.assertEqual(result.stripped_lines, [], result.diagnostics)
                self.assertEqual(result.exit_code, 0, result.diagnostics)

    def test_removed_checker_is_not_in_the_tree(self):
        matches = [
            path.relative_to(ROOT).as_posix()
            for path in ROOT.rglob("check_markdown_bullets.py")
            if ".git" not in path.parts
        ]
        self.assertEqual(matches, [])

    def test_license_is_mit(self):
        text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", text)
        self.assertIn("Permission is hereby granted", text)

    def test_no_out_of_scope_claims(self):
        # Host-adaptation docs may name WorkBuddy; the ban was for unsolicited claims.
        needles = (
            "408" + "-codex-plugin",
            "竞" + "品",
            "human" + "ize",
        )
        scanned = []
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if any(part in {".git", "__pycache__"} for part in path.parts):
                continue
            if path.suffix.lower() not in {".md", ".py", ".yml", ".json", ".txt"}:
                continue
            scanned.append(path)
            text = path.read_text(encoding="utf-8")
            for needle in needles:
                self.assertNotIn(needle, text, f"{path} contains {needle}")
        self.assertTrue(scanned)


if __name__ == "__main__":
    unittest.main()
