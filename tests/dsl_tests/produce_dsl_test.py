import unittest

import neurosym as ns

from imperative_stitch.parser import converter
from imperative_stitch.utils.classify_nodes import export_dfa
from imperative_stitch.utils.export_as_dsl import DSLSubset, create_dsl

from ..utils import assertDSL


class ProduceDslTest(unittest.TestCase):
    def setUp(self):
        self.dfa = export_dfa()

    def test_produce_dsl_basic(self):
        program = ns.python_to_python_ast("x = x + 2; y = y + x + 2")
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
        program = ns.python_to_python_ast("x: List[int, int] = 2")
        print(ns.render_s_expression(program.to_ns_s_exp()))
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
            converter.s_exp_to_python_ast(p)
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
        program = ns.python_to_python_ast("x:int = 5; y: float=5")
        subset = DSLSubset.from_program(self.dfa, program, root="M")
        create_dsl(export_dfa(), subset, "M")
