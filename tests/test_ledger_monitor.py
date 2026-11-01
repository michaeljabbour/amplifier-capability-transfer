"""Offline queue-integrity and regression-oracle fixtures; no transfer execution."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
from fitness import fitness, read_rows
from hillclimb import check, main


class LedgerMonitorTests(unittest.TestCase):
    def test_deleted_implemented_cannot_be_hidden_by_other_progress(self):
        ok, _ = check([
            [("a", "host", "implemented"), ("b", "host", "new")],
            [("b", "host", "implemented")],
        ])
        self.assertFalse(ok)

    def test_deleted_new_row_cannot_inflate_score(self):
        ok, _ = check([
            [("a", "host", "implemented"), ("b", "host", "new")],
            [("a", "host", "implemented")],
        ])
        self.assertFalse(ok)

    def test_changed_target_does_not_reuse_another_hosts_evidence(self):
        for verifier in (False, True):
            with self.subTest(verifier=verifier):
                self.assertFalse(check([
                    [("a", "hostA", "implemented")],
                    [("a", "hostB", "implemented")],
                ], verifier=verifier)[0])

    def test_duplicate_keys_are_invalid_even_with_same_target(self):
        rows = [("a", "host", "implemented"), ("a", "host", "implemented")]
        with self.assertRaises(ValueError):
            fitness(rows)
        self.assertFalse(check([rows])[0])

    def test_unknown_state_is_invalid(self):
        rows = [("a", "host", "mystery")]
        with self.assertRaises(ValueError):
            fitness(rows)
        self.assertFalse(check([rows])[0])

    def test_blank_key_or_target_is_invalid(self):
        for rows in [[("", "host", "new")], [("a", "", "new")]]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                fitness(rows)

    def test_wrong_width_is_invalid(self):
        for row in [("a", "host"), ("a", "host", "new", "extra")]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                fitness([row])

    def test_missing_snapshots_do_not_prove_a_run(self):
        self.assertFalse(check([])[0])

    def test_empty_ledger_is_a_valid_empty_queue(self):
        self.assertEqual(fitness([])["total"], 0)
        self.assertTrue(check([[]])[0])

    def test_verifier_may_reopen_implemented_row(self):
        self.assertTrue(check([
            [("a", "host", "implemented")],
            [("a", "host", "new")],
        ], verifier=True)[0])

    def test_builder_reopen_cannot_be_compensated(self):
        self.assertFalse(check([
            [("a", "host", "implemented"), ("b", "host", "new")],
            [("a", "host", "new"), ("b", "host", "implemented")],
        ])[0])

    def test_verified_terminal_cannot_be_removed_or_reopened(self):
        for next_rows in [[], [("a", "host", "implemented")]]:
            with self.subTest(next_rows=next_rows):
                self.assertFalse(check([
                    [("a", "host", "verified")], next_rows,
                ], verifier=True)[0])

    def test_new_distinct_rows_are_allowed_without_reassigning_existing_work(self):
        self.assertTrue(check([
            [("a", "host", "new")],
            [("a", "host", "implemented"), ("b", "hostB", "new")],
        ])[0])

    def test_reader_accepts_comments_blanks_and_valid_states(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ledger.tsv"
            p.write_text("# fictional\n\na\thost\tnew\nb\thost\tacknowledged\n")
            self.assertEqual(read_rows(str(p)), [("a", "host", "new"), ("b", "host", "acknowledged")])

    def test_reader_rejects_malformed_instead_of_dropping_rows(self):
        for line in ["a\thost", "a\thost\tnew\textra", "a\thost\tmystery", "\thost\tnew", "a\t\tnew", "a\thost\tnew\na\thost\tverified"]:
            with self.subTest(line=line), tempfile.TemporaryDirectory() as d:
                p = Path(d) / "ledger.tsv"
                p.write_text(line + "\n")
                with self.assertRaises(ValueError):
                    read_rows(str(p))

    def test_cli_invalid_ledger_is_nonzero_and_never_climbing(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "invalid.tsv"
            p.write_text("a\thost\tmystery\n")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                result = main([str(p)])
            self.assertNotEqual(result, 0)
            self.assertNotIn("CLIMBING", out.getvalue())
            self.assertIn("invalid", err.getvalue().lower())

if __name__ == "__main__":
    unittest.main()
