import unittest

import neurosym as ns

from imperative_stitch.utils.classify_nodes import export_dfa
from imperative_stitch.utils.export_as_dsl import DSLSubset


class DSLSubsetTest(unittest.TestCase):
    def setUp(self):
        self.dfa = export_dfa()

    def test_subset_basic(self):
        subset = DSLSubset.from_program(
            self.dfa,
            ns.python_to_python_ast("x = x + 2; y = y + x + 2"),
            root="M",
        )
        print(subset)
        self.assertEqual(
            subset,
            DSLSubset(
                lengths_by_sequence_type={"seqS": [2], "[L]": [1], "[TI]": [0]},
                leaves={
                    "Name": ["const-&x:0", "const-&y:0"],
                    "Ctx": ["Load", "Store"],
                    "O": ["Add"],
                    "Const": ["const-i2"],
                    "ConstKind": ["const-None"],
                    "TC": ["const-None"],
                },
                include_dbvars=False,
            ),
        )

    def test_subset_multi_length(self):
        subset = DSLSubset.from_program(
            self.dfa,
            ns.python_to_python_ast("x = [1, 2, 3]; y = [1, 2, 3, 4]"),
            root="M",
        )
        print(subset)
        self.assertEqual(
            subset,
            DSLSubset(
                lengths_by_sequence_type={
                    "seqS": [2],
                    "[L]": [1],
                    "[StarredRoot]": [3, 4],
                    "[TI]": [0],
                },
                leaves={
                    "Name": ["const-&x:0", "const-&y:0"],
                    "Ctx": ["Load", "Store"],
                    "Const": ["const-i1", "const-i2", "const-i3", "const-i4"],
                    "ConstKind": ["const-None"],
                    "TC": ["const-None"],
                },
                include_dbvars=False,
            ),
        )

    def test_subset_multi_root(self):
        subset = DSLSubset.from_program(
            self.dfa,
            ns.python_to_python_ast("x = x + 2; y = y + x + 2"),
            ns.python_statement_to_python_ast("while True: pass"),
            root=("M", "S"),
        )
        print(subset)
        self.assertEqual(
            subset,
            DSLSubset(
                lengths_by_sequence_type={"seqS": [0, 1, 2], "[L]": [1], "[TI]": [0]},
                leaves={
                    "Name": ["const-&x:0", "const-&y:0"],
                    "Ctx": ["Load", "Store"],
                    "O": ["Add"],
                    "Const": ["const-True", "const-i2"],
                    "ConstKind": ["const-None"],
                    "TC": ["const-None"],
                    "S": ["Pass"],
                },
                include_dbvars=False,
            ),
        )

    def test_subset_fill_in_missing(self):
        subset = DSLSubset.from_program(
            self.dfa,
            ns.python_to_python_ast("x = x + 2; y = y + x + 2"),
            ns.python_to_python_ast("x = 2; y = 3; z = 4; a = 7"),
            root=("M", "M"),
        )
        print(subset)
        self.assertEqual(
            subset.lengths_by_sequence_type, {"seqS": [2, 4], "[L]": [1], "[TI]": [0]}
        )
        subset = subset.fill_in_missing_lengths()
        print(subset)
        self.assertEqual(
            subset.lengths_by_sequence_type,
            {"seqS": [2, 3, 4], "[L]": [1], "[TI]": [0]},
        )
