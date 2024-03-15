import unittest
from fractions import Fraction

import neurosym as ns
import numpy as np

from imperative_stitch.parser.convert import s_exp_to_python
from imperative_stitch.parser.parsed_ast import ParsedAST
from imperative_stitch.utils.classify_nodes import export_dfa
from imperative_stitch.utils.export_as_dsl import DSLSubset, create_dsl

from ..utils import assertDSL


class SubsetTest(unittest.TestCase):
    def setUp(self):
        self.dfa = export_dfa()

    def test_subset_basic(self):
        subset = DSLSubset.from_program(
            self.dfa,
            ParsedAST.parse_python_module("x = x + 2; y = y + x + 2"),
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
            ),
        )

    def test_subset_multi_length(self):
        subset = DSLSubset.from_program(
            self.dfa,
            ParsedAST.parse_python_module("x = [1, 2, 3]; y = [1, 2, 3, 4]"),
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
            ),
        )


class ProduceDslTest(unittest.TestCase):
    def setUp(self):
        self.dfa = export_dfa()

    def test_produce_dsl_basic(self):
        program = ParsedAST.parse_python_module("x = x + 2; y = y + x + 2")
        subset = DSLSubset.from_program(self.dfa, program, root="M")
        dsl = create_dsl(export_dfa(), subset, "M")
        assertDSL(
            self,
            dsl.render(),
            """
            /choiceseq~seqS~2 :: (S, S) -> seqS
            /seq~seqS~2 :: (S, S) -> seqS
            /splice~S :: seqS -> S
            Add~O :: () -> O
            Assert~S :: (E, E) -> S
            Assign~S :: ([L], E, TC) -> S
            AsyncFor~S :: (L, E, seqS, seqS, TC) -> S
            AugAssign~S :: (L, O, E) -> S
            Await~E :: E -> E
            BinOp~E :: (E, O, E) -> E
            Constant~E :: (Const, ConstKind) -> E
            Delete~S :: [L] -> S
            Expr~S :: E -> S
            For~S :: (L, E, seqS, seqS, TC) -> S
            IfExp~E :: (E, E, E) -> E
            If~S :: (E, seqS, seqS) -> S
            List~L :: ([L], Ctx) -> L
            Load~Ctx :: () -> Ctx
            Module~M :: (seqS, [TI]) -> M
            NamedExpr~E :: (L, E) -> E
            Name~E :: (Name, Ctx) -> E
            Name~L :: (Name, Ctx) -> L
            Raise~S :: (E, E) -> S
            Return~S :: E -> S
            Slice~Slice :: (E, E, E) -> Slice
            Starred~E :: (E, Ctx) -> E
            Starred~L :: (L, L) -> L
            Starred~Starred :: (E, Ctx) -> Starred
            Store~Ctx :: () -> Ctx
            Subscript~E :: (E, SliceRoot, Ctx) -> E
            Subscript~L :: (E, SliceRoot, Ctx) -> L
            Tuple~L :: ([L], Ctx) -> L
            UnaryOp~E :: (O, E) -> E
            While~S :: (E, seqS, seqS) -> S
            YieldFrom~E :: E -> E
            Yield~E :: E -> E
            _slice_content~SliceRoot :: E -> SliceRoot
            _slice_slice~SliceRoot :: Slice -> SliceRoot
            _starred_content~L :: L -> L
            _starred_starred~L :: Starred -> L
            const-&x:0~Name :: () -> Name
            const-&y:0~Name :: () -> Name
            const-None~ConstKind :: () -> ConstKind
            const-None~TC :: () -> TC
            const-i2~Const :: () -> Const
            list~_L_~1 :: L -> [L]
            list~_TI_~0 :: () -> [TI]
            """,
        )

    def test_fit_to_programs_including_abstractions(self):
        new_dfa = {"E": {}, "seqS": {}}
        new_dfa["E"]["fn_1"] = []
        new_dfa["E"]["fn_2"] = ["seqS"]
        new_dfa["seqS"]["fn_param_1"] = ["E"]
        test_programs = [
            ParsedAST.parse_s_expression(p)
            for p in ["(fn_1)", "(fn_2 (fn_param_1 (fn_1)))"]
        ]
        new_subset = DSLSubset.from_program(new_dfa, *test_programs, root="E")
        new_dsl = create_dsl(new_dfa, new_subset, "E")
        assertDSL(
            self,
            new_dsl.render(),
            """
            fn_1~E :: () -> E
            fn_2~E :: seqS -> E
            fn_param_1~seqS :: E -> seqS
            """,
        )


def fit_to(programs):
    dfa = export_dfa()
    programs = [ParsedAST.parse_python_module(p) for p in programs]
    subset = DSLSubset.from_program(dfa, *programs, root="M")
    dsl = create_dsl(export_dfa(), subset, "M")
    fam = ns.BigramProgramDistributionFamily(dsl)
    counts = fam.count_programs(
        [[program.to_type_annotated_ns_s_exp(dfa, "M") for program in programs]]
    )
    dist = fam.counts_to_distribution(counts)[0]
    return fam, dist


class EnumerateFittedDslTest(unittest.TestCase):
    def enumerate(self, *programs):
        fam, dist = fit_to(programs)
        out = [
            (
                Fraction.from_float(np.exp(y)).limit_denominator(),
                s_exp_to_python(ns.render_s_expression(x)),
            )
            for x, y in fam.enumerate(dist, min_likelihood=-10)
        ]
        out = sorted(out, key=lambda x: (-x[0], x[1]))
        print(out)
        return out

    def test_enumerate_fitted_dsl_basic(self):
        self.assertEqual(
            self.enumerate("x = x + 2 + 2"),
            [
                (Fraction(1, 2), "x = x + 2"),
                (Fraction(1, 4), "x = x + 2 + 2"),
                (Fraction(1, 8), "x = x + 2 + 2 + 2"),
                (Fraction(1, 16), "x = x + 2 + 2 + 2 + 2"),
                (Fraction(1, 32), "x = x + 2 + 2 + 2 + 2 + 2"),
                (Fraction(1, 64), "x = x + 2 + 2 + 2 + 2 + 2 + 2"),
                (Fraction(1, 128), "x = x + 2 + 2 + 2 + 2 + 2 + 2 + 2"),
                (Fraction(1, 256), "x = x + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2"),
                (Fraction(1, 512), "x = x + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2"),
                (Fraction(1, 1024), "x = x + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2"),
                (
                    Fraction(1, 2048),
                    "x = x + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2",
                ),
                (
                    Fraction(1, 4096),
                    "x = x + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2",
                ),
                (
                    Fraction(1, 8192),
                    "x = x + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2",
                ),
                (
                    Fraction(1, 16384),
                    "x = x + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2",
                ),
            ],
        )

    def test_enumerate_fitted_dsl_cartesian(self):
        self.assertEqual(
            self.enumerate("x = 2", "y = 3"),
            [
                (Fraction(1, 4), "x = 2"),
                (Fraction(1, 4), "x = 3"),
                (Fraction(1, 4), "y = 2"),
                (Fraction(1, 4), "y = 3"),
            ],
        )
