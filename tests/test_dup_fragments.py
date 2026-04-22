import unittest
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from lesspython.core import scan_folder


@dataclass(frozen=True)
class ScanResult:
    groups_count: int
    errors_count: int
    python_files: int


def run_scan(
    folder: Path,
    min_lines: int,
    normalize_literals: bool = False,
    exclude: list[Path] | None = None,
) -> ScanResult:
    report = scan_folder(
        folder,
        min_lines=min_lines,
        normalize_literals=normalize_literals,
        exclude_paths=exclude,
    )
    return ScanResult(
        groups_count=len(report.groups),
        errors_count=len(report.errors),
        python_files=report.python_files,
    )


class TestDupFragments(unittest.TestCase):
    def test_variable_name_duplicates_detected(self) -> None:
        folder = ROOT / "examples" / "basic"
        result = run_scan(folder, min_lines=5)
        self.assertGreater(result.groups_count, 0)

    def test_class_name_duplicates_detected(self) -> None:
        folder = ROOT / "examples" / "classes"
        result = run_scan(folder, min_lines=4)
        self.assertGreater(result.groups_count, 0)

    def test_if_else_duplicates_detected(self) -> None:
        folder = ROOT / "examples" / "if_else"
        result = run_scan(folder, min_lines=4)
        self.assertGreater(result.groups_count, 0)

    def test_loop_duplicates_detected(self) -> None:
        folder = ROOT / "examples" / "loops"
        result = run_scan(folder, min_lines=4)
        self.assertGreater(result.groups_count, 0)

    def test_async_function_duplicates_detected(self) -> None:
        folder = ROOT / "examples" / "async"
        result = run_scan(folder, min_lines=4)
        self.assertGreater(result.groups_count, 0)

    def test_with_statement_duplicates_detected(self) -> None:
        folder = ROOT / "examples" / "with_ctx"
        result = run_scan(folder, min_lines=4)
        self.assertGreater(result.groups_count, 0)

    def test_literals_normalization_option(self) -> None:
        folder = ROOT / "examples" / "literals"
        result = run_scan(folder, min_lines=3, normalize_literals=False)
        self.assertEqual(result.groups_count, 0)

        result = run_scan(folder, min_lines=3, normalize_literals=True)
        self.assertGreater(result.groups_count, 0)

    def test_sequence_detection(self) -> None:
        folder = ROOT / "examples" / "sequence"
        result = run_scan(folder, min_lines=3)
        self.assertGreater(result.groups_count, 0)

    def test_expression_sequence_collapses_adjacent_duplicates(self) -> None:
        folder = ROOT / "examples" / "arg_sequence"
        report = scan_folder(folder, min_lines=4, normalize_literals=False)
        self.assertEqual(len(report.groups), 1)
        self.assertTrue(
            all(
                occ.node_type.startswith("ExprSequence")
                for group in report.groups
                for occ in group.occurrences
            )
        )

    def test_sequence_includes_loop_summary_assignment(self) -> None:
        folder = ROOT / "examples" / "loop_summary"
        report = scan_folder(folder, min_lines=4, normalize_literals=False)
        target_file = folder / "summary.py"
        lines = target_file.read_text(encoding="utf-8").splitlines()
        start_line = next(
            i + 1 for i, line in enumerate(lines) if line.strip() == "data = [1, 2, 3]"
        )
        summary_line = next(
            i + 1
            for i, line in enumerate(lines)
            if line.strip()
            == "summary = [(name, count) for name, count in counts.items()]"
        )
        self.assertTrue(
            any(
                occ.path == target_file
                and occ.lineno == start_line
                and occ.end_lineno >= summary_line
                for group in report.groups
                for occ in group.occurrences
            )
        )

    def test_sequence_rejects_swapped_cross_statement_usage(self) -> None:
        folder = ROOT / "examples" / "hybrid_swap"
        result = run_scan(folder, min_lines=4)
        self.assertEqual(result.groups_count, 0)

    def test_attribute_names_not_normalized(self) -> None:
        folder = ROOT / "examples" / "attributes"
        result = run_scan(folder, min_lines=4)
        self.assertEqual(result.groups_count, 0)

    def test_min_lines_threshold(self) -> None:
        folder = ROOT / "examples" / "basic"
        result = run_scan(folder, min_lines=50)
        self.assertEqual(result.groups_count, 0)

    def test_no_python_files(self) -> None:
        folder = ROOT / "examples" / "none"
        result = run_scan(folder, min_lines=3)
        self.assertEqual(result.python_files, 0)
        self.assertEqual(result.groups_count, 0)

    def test_errors_reported_and_duplicates_still_found(self) -> None:
        folder = ROOT / "examples" / "errors"
        result = run_scan(folder, min_lines=4)
        self.assertGreater(result.errors_count, 0)
        self.assertGreater(result.groups_count, 0)

    def test_class_body_annotations_not_duplicated(self) -> None:
        folder = ROOT / "examples" / "classes"
        result = run_scan(
            folder,
            min_lines=5,
            exclude=[Path("class_dup.py")],
        )
        self.assertEqual(result.groups_count, 0)

    def test_cross_file_duplicates_detected(self) -> None:
        folder = ROOT / "examples" / "cross"
        result = run_scan(folder, min_lines=4)
        self.assertGreater(result.groups_count, 0)

    def test_exclude_paths_skips_duplicates(self) -> None:
        folder = ROOT / "examples" / "exclude"
        result = run_scan(folder, min_lines=3, exclude=[Path("ex2.py")])
        self.assertEqual(result.groups_count, 0)

    def test_try_except_duplicates_detected(self) -> None:
        folder = ROOT / "examples" / "try_except"
        result = run_scan(folder, min_lines=4)
        self.assertGreater(result.groups_count, 0)

    def test_match_case_duplicates_detected(self) -> None:
        folder = ROOT / "examples" / "match_case"
        result = run_scan(folder, min_lines=4)
        self.assertGreater(result.groups_count, 0)

    def test_blank_lines_ignored_for_min_lines(self) -> None:
        folder = ROOT / "examples" / "blank_lines"
        result = run_scan(folder, min_lines=4)
        self.assertGreater(result.groups_count, 0)

    def test_comment_lines_ignored_for_min_lines(self) -> None:
        folder = ROOT / "examples" / "comments"
        result = run_scan(folder, min_lines=4)
        self.assertGreater(result.groups_count, 0)

    def test_assignment_groups_not_alpha_equivalent(self) -> None:
        folder = ROOT / "examples" / "assignments"
        result = run_scan(folder, min_lines=5)
        self.assertGreater(result.groups_count, 0)
        report = scan_folder(folder, min_lines=5, normalize_literals=False)
        self.assertTrue(
            any(
                {occ.path.name for occ in group.occurrences}
                >= {"assi.py", "assi2.py"}
                for group in report.groups
            )
        )

    def test_ignore_comment_skips_block(self) -> None:
        folder = ROOT / "examples" / "ignore"
        result = run_scan(folder, min_lines=4)
        self.assertEqual(result.groups_count, 0)

    def test_ignore_comment_in_nested_block(self) -> None:
        folder = ROOT / "examples" / "ignore_nested"
        result = run_scan(folder, min_lines=3)
        self.assertGreater(result.groups_count, 0)

    def test_class_attribute_names_not_duplicated(self) -> None:
        folder = ROOT / "examples" / "class_attributes"
        result = run_scan(folder, min_lines=3)
        self.assertEqual(result.groups_count, 0)

    def test_instance_attribute_names_not_duplicated(self) -> None:
        folder = ROOT / "examples" / "attributes_instance"
        result = run_scan(folder, min_lines=3)
        self.assertEqual(result.groups_count, 0)

    def test_non_equivalent_literals_not_duplicated(self) -> None:
        folder = ROOT / "examples" / "noise"
        result = run_scan(folder, min_lines=3)
        self.assertEqual(result.groups_count, 0)

    def test_closure_renaming_detected(self) -> None:
        folder = ROOT / "examples" / "closure"
        result = run_scan(folder, min_lines=3)
        self.assertGreater(result.groups_count, 0)

    def test_dict_literal_keys_not_duplicated(self) -> None:
        folder = ROOT / "examples" / "dict_literals"
        result = run_scan(folder, min_lines=3)
        self.assertEqual(result.groups_count, 0)

    def test_loop_operation_difference_not_duplicated(self) -> None:
        folder = ROOT / "examples" / "loops_negative"
        result = run_scan(folder, min_lines=3)
        self.assertEqual(result.groups_count, 0)

    def test_shadowing_alpha_equivalent(self) -> None:
        folder = ROOT / "examples" / "shadowing"
        result = run_scan(folder, min_lines=3)
        self.assertGreater(result.groups_count, 0)

    def test_nonlocal_alpha_equivalent(self) -> None:
        folder = ROOT / "examples" / "nonlocal"
        result = run_scan(folder, min_lines=3)
        self.assertGreater(result.groups_count, 0)

    def test_comprehension_alpha_equivalent(self) -> None:
        folder = ROOT / "examples" / "comprehension"
        result = run_scan(folder, min_lines=2)
        self.assertGreater(result.groups_count, 0)

    def test_with_except_alpha_equivalent(self) -> None:
        folder = ROOT / "examples" / "with_except"
        result = run_scan(folder, min_lines=3)
        self.assertGreater(result.groups_count, 0)

    def test_pattern_binding_alpha_equivalent(self) -> None:
        folder = ROOT / "examples" / "patterns"
        result = run_scan(folder, min_lines=3)
        self.assertGreater(result.groups_count, 0)

    def test_free_name_vs_bound_not_equivalent(self) -> None:
        folder = ROOT / "examples" / "free_names"
        result = run_scan(folder, min_lines=2)
        self.assertEqual(result.groups_count, 0)

    def test_nonlocal_mismatch_not_equivalent(self) -> None:
        folder = ROOT / "examples" / "nonlocal"
        result = run_scan(folder, min_lines=3, exclude=[Path("nonlocal_example.py")])
        self.assertEqual(result.groups_count, 0)

    def test_global_alpha_equivalent(self) -> None:
        folder = ROOT / "examples" / "global"
        result = run_scan(folder, min_lines=3)
        self.assertEqual(result.groups_count, 0)

    def test_global_conditional_duplicates_detected(self) -> None:
        folder = ROOT / "examples" / "global_conditional"
        result = run_scan(folder, min_lines=4)
        self.assertGreater(result.groups_count, 0)

    def test_imports_ignored(self) -> None:
        folder = ROOT / "examples" / "imports"
        result = run_scan(folder, min_lines=2)
        self.assertGreater(result.groups_count, 0)

    def test_attribute_vs_local_not_equivalent(self) -> None:
        folder = ROOT / "examples" / "attr_vs_local"
        result = run_scan(folder, min_lines=3)
        self.assertEqual(result.groups_count, 0)

if __name__ == "__main__":
    unittest.main()
