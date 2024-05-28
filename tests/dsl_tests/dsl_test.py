import unittest
from fractions import Fraction

import neurosym as ns
import numpy as np

from imperative_stitch.utils.classify_nodes import export_dfa
from imperative_stitch.utils.def_use_mask import DefUseChainPreorderMask
from imperative_stitch.utils.def_use_mask.ordering import PythonNodeOrdering
from imperative_stitch.utils.export_as_dsl import (
    DSLSubset,
    create_dsl,
    create_smoothing_mask,
)

from ..utils import assertDSL


class SubsetTest(unittest.TestCase):
    def setUp(self):
        self.dfa = export_dfa()

    def test_subset_basic(self):
        subset = DSLSubset.from_program(
            self.dfa,
            ns.PythonAST.parse_python_module("x = x + 2; y = y + x + 2"),
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
            ns.PythonAST.parse_python_module("x = [1, 2, 3]; y = [1, 2, 3, 4]"),
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
            ns.PythonAST.parse_python_module("x = x + 2; y = y + x + 2"),
            ns.PythonAST.parse_python_statement("while True: pass"),
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
            ns.PythonAST.parse_python_module("x = x + 2; y = y + x + 2"),
            ns.PythonAST.parse_python_module("x = 2; y = 3; z = 4; a = 7"),
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


class ProduceDslTest(unittest.TestCase):
    def setUp(self):
        self.dfa = export_dfa()

    def test_produce_dsl_basic(self):
        program = ns.PythonAST.parse_python_module("x = x + 2; y = y + x + 2")
        subset = DSLSubset.from_program(self.dfa, program, root="M")
        dsl = create_dsl(export_dfa(), subset, "M")
        assertDSL(
            self,
            dsl.render(),
            """
            /choiceseq~seqS~2 :: (S, S) -> seqS
            /seq~seqS~2 :: (S, S) -> seqS
            /splice~S :: seqS -> S
            /subseq~seqS~2 :: (S, S) -> seqS
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
            Starred~L :: (L, Ctx) -> L
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
            _starred_starred~L :: L -> L
            const-&x:0~Name :: () -> Name
            const-&y:0~Name :: () -> Name
            const-None~ConstKind :: () -> ConstKind
            const-None~TC :: () -> TC
            const-i2~Const :: () -> Const
            list~_L_~1 :: L -> [L]
            list~_TI_~0 :: () -> [TI]
            """,
        )

    def test_produce_dsl_bad_type_annotate_length(self):
        program = ns.PythonAST.parse_python_module("x: List[int, int] = 2")
        print(program.to_s_exp())
        subset = DSLSubset.from_program(self.dfa, program, root="M")
        dsl = create_dsl(export_dfa(), subset, "M")
        ta_lines = {x.strip() for x in dsl.render().split("\n") if "list~TA" in x}
        self.assertEqual(ta_lines, {"list~TA~2 :: (TA, TA) -> TA"})

    def test_fit_to_programs_including_abstractions(self):
        new_dfa = {"E": {}, "seqS": {}}
        new_dfa["E"]["fn_1"] = []
        new_dfa["E"]["fn_2"] = ["seqS"]
        new_dfa["seqS"]["fn_param_1"] = ["E"]
        test_programs = [
            ns.PythonAST.parse_s_expression(p)
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

    def test_create_dsl_with_type_annot(self):
        # just check it doesn't crash
        program = ns.PythonAST.parse_python_module("x:int = 5; y: float=5")
        subset = DSLSubset.from_program(self.dfa, program, root="M")
        create_dsl(export_dfa(), subset, "M")


def fit_to(
    programs,
    parser=ns.PythonAST.parse_python_module,
    root="M",
    abstrs=(),
    use_def_use=True,
    use_node_ordering=True,
    smoothing=True,
    include_type_preorder_mask=True,
):
    """
    Set include_type_preorder_mask to False to disable the type preorder mask,
        this is basically only useful in the specific context where we are testing
        the names mask and want no other masks to be applied.
    """
    dfa = export_dfa(abstrs=abstrs)
    programs = [parser(p) for p in programs]
    dsl = create_dsl(
        dfa, DSLSubset.from_program(dfa, *programs, root=root, abstrs=abstrs), root
    )
    dsl_subset = create_dsl(
        dfa, DSLSubset.from_program(dfa, *programs, root=root), root
    )
    smooth_mask = create_smoothing_mask(dsl, dsl_subset)
    apms = [
        lambda dist, dsl: DefUseChainPreorderMask(dist, dsl, dfa=dfa, abstrs=abstrs)
    ]
    node_ordering = (
        (lambda dist: PythonNodeOrdering(dist, abstrs))
        if use_node_ordering
        else ns.DefaultNodeOrdering
    )
    fam = ns.BigramProgramDistributionFamily(
        dsl,
        additional_preorder_masks=apms if use_def_use else [],
        include_type_preorder_mask=include_type_preorder_mask,
        node_ordering=node_ordering,
    )
    counts = fam.count_programs(
        [[program.to_type_annotated_ns_s_exp(dfa, root) for program in programs]]
    )
    dist = fam.counts_to_distribution(counts)[0]
    if smoothing:
        dist = dist.bound_minimum_likelihood(1e-4, smooth_mask)
    return dfa, dsl, fam, dist


class EnumerateFittedDslTest(unittest.TestCase):
    def enumerate(self, *programs):
        _, _, fam, dist = fit_to(programs, smoothing=False)
        out = [
            (
                Fraction.from_float(np.exp(y)).limit_denominator(),
                ns.s_exp_to_python(ns.render_s_expression(x)),
            )
            for x, y in fam.enumerate(dist, min_likelihood=-10)
        ]
        out = sorted(out, key=lambda x: (-x[0], x[1]))
        print(out)
        return out

    def test_enumerate_fitted_dsl_basic(self):
        self.assertEqual(
            self.enumerate("x = y + 2 + 2"),
            [
                (Fraction(1, 2), "x = y + 2"),
                (Fraction(1, 4), "x = y + 2 + 2"),
                (Fraction(1, 8), "x = y + 2 + 2 + 2"),
                (Fraction(1, 16), "x = y + 2 + 2 + 2 + 2"),
                (Fraction(1, 32), "x = y + 2 + 2 + 2 + 2 + 2"),
                (Fraction(1, 64), "x = y + 2 + 2 + 2 + 2 + 2 + 2"),
                (Fraction(1, 128), "x = y + 2 + 2 + 2 + 2 + 2 + 2 + 2"),
                (Fraction(1, 256), "x = y + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2"),
                (Fraction(1, 512), "x = y + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2"),
                (Fraction(1, 1024), "x = y + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2"),
                (
                    Fraction(1, 2048),
                    "x = y + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2",
                ),
                (
                    Fraction(1, 4096),
                    "x = y + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2",
                ),
                (
                    Fraction(1, 8192),
                    "x = y + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2",
                ),
                (
                    Fraction(1, 16384),
                    "x = y + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 2",
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

    def test_enumerate_def_use_check(self):
        self.assertEqual(
            self.enumerate("x = 2; y = x", "y = 2; x = y"),
            [
                (Fraction(1, 8), "x = 2\nx = 2"),
                (Fraction(1, 8), "x = 2\nx = x"),
                (Fraction(1, 8), "x = 2\ny = 2"),
                (Fraction(1, 8), "x = 2\ny = x"),
                (Fraction(1, 8), "y = 2\nx = 2"),
                (Fraction(1, 8), "y = 2\nx = y"),
                (Fraction(1, 8), "y = 2\ny = 2"),
                (Fraction(1, 8), "y = 2\ny = y"),
            ],
        )

    def test_enumerate_def_use_check_wglobal(self):
        self.assertEqual(
            self.enumerate("x = print; y = x", "y = print; x = y"),
            [
                (Fraction(1, 6), "x = print\nx = print"),
                (Fraction(1, 6), "x = print\ny = print"),
                (Fraction(1, 6), "y = print\nx = print"),
                (Fraction(1, 6), "y = print\ny = print"),
                (Fraction(1, 12), "x = print\nx = x"),
                (Fraction(1, 12), "x = print\ny = x"),
                (Fraction(1, 12), "y = print\nx = y"),
                (Fraction(1, 12), "y = print\ny = y"),
            ],
        )


class TestLikelihoodFittedDSL(unittest.TestCase):
    def compute_likelihood(self, corpus, program):
        dfa, _, fam, dist = fit_to(corpus, smoothing=False)
        program = ns.PythonAST.parse_python_module(program).to_type_annotated_ns_s_exp(
            dfa, "M"
        )
        like = fam.compute_likelihood(dist, program)
        like = Fraction.from_float(float(np.exp(like))).limit_denominator()
        results = fam.compute_likelihood_per_node(dist, program)
        results = [
            (
                ns.render_s_expression(x),
                Fraction.from_float(float(np.exp(y))).limit_denominator(),
            )
            for x, y in results
            if y != 0  # remove zero log-likelihoods
        ]
        print(like)
        print(results)
        return like, results

    def test_likelihood(self):
        like, results = self.compute_likelihood(["x = 2", "y = 3", "y = 4"], "y = 4")
        self.assertAlmostEqual(like, Fraction(2, 9))
        self.assertEqual(
            results,
            [
                ("(const-&y:0~Name)", Fraction(2, 3)),
                ("(const-i4~Const)", Fraction(1, 3)),
            ],
        )

    def test_likelihood_def_use_check(self):
        like, results = self.compute_likelihood(
            ["x = 2; y = x", "y = 2; x = y"], "x = 2; y = x"
        )
        self.assertAlmostEqual(like, Fraction(1, 8))
        self.assertEqual(
            results,
            [
                ("(const-&x:0~Name)", Fraction(1, 2)),
                ("(const-&y:0~Name)", Fraction(1, 2)),
                ("(Name~E (const-&x:0~Name) (Load~Ctx))", Fraction(1, 2)),
            ],
        )

    def test_likelihood_zero(self):
        like, results = self.compute_likelihood(
            ["y = x + 2", "y = 2 + 3", "y = 4"], "y = 2 + x"
        )
        self.assertAlmostEqual(like, Fraction(0))
        self.assertEqual(
            results,
            [
                (
                    "(BinOp~E (Constant~E (const-i2~Const) (const-None~ConstKind)) (Add~O) (Name~E (const-g_x~Name) (Load~Ctx)))",
                    Fraction(2, 3),
                ),
                (
                    "(Constant~E (const-i2~Const) (const-None~ConstKind))",
                    Fraction(1, 2),
                ),
                ("(const-i2~Const)", Fraction(1, 2)),
                ("(Name~E (const-g_x~Name) (Load~Ctx))", Fraction(0, 1)),
            ],
        )

    def test_likelihood_with_abstractions(self):
        # test from annie
        # I don't think it actually makes sense since (fn_3) shouldn't be possible
        test_programs = ["(fn_1 (fn_2) (fn_2))", "(fn_1 (fn_3 (fn_3)) (fn_3))"]
        test_programs_ast = [ns.PythonAST.parse_s_expression(p) for p in test_programs]
        test_dfa = {"E": {"fn_1": ["E", "E"], "fn_2": [], "fn_3": ["E"]}}

        test_subset = DSLSubset.from_program(
            test_dfa,
            *test_programs_ast,
            root="E",
        )
        test_dsl = create_dsl(test_dfa, test_subset, "E")

        test_fam = ns.BigramProgramDistributionFamily(test_dsl)
        test_counts = test_fam.count_programs(
            [[test_programs_ast[0].to_type_annotated_ns_s_exp(test_dfa, "E")]]
        )
        test_dist = test_fam.counts_to_distribution(test_counts)[0]
        likelihood = test_fam.compute_likelihood(
            test_dist, test_programs_ast[1].to_type_annotated_ns_s_exp(test_dfa, "E")
        )
        self.assertEqual(likelihood, -np.inf)
        result = test_fam.compute_likelihood_per_node(
            test_dist, test_programs_ast[1].to_type_annotated_ns_s_exp(test_dfa, "E")
        )
        result = [
            (
                ns.render_s_expression(x),
                Fraction.from_float(float(np.exp(y))).limit_denominator(),
            )
            for x, y in result
            if y != 0  # remove zero log-likelihoods
        ]
        self.assertEqual(
            result,
            [
                ("(fn_3~E (fn_3~E))", Fraction(0, 1)),
                ("(fn_3~E)", Fraction(0, 1)),
                ("(fn_3~E)", Fraction(0, 1)),
            ],
        )
