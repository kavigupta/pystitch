import ast
import re
import unittest
from fractions import Fraction

import neurosym as ns
import numpy as np

from imperative_stitch.analyze_program.ssa.banned_component import (
    BannedComponentError,
    check_banned_components,
)
from imperative_stitch.parser.parsed_ast import ParsedAST
from imperative_stitch.utils.classify_nodes import export_dfa
from imperative_stitch.utils.def_use_mask.ordering import PythonNodeOrdering
from imperative_stitch.utils.export_as_dsl import DSLSubset, create_dsl
from tests.utils import cwq, expand_with_slow_tests, small_set_runnable_code_examples


class CanonicalizeDeBruijnTest(unittest.TestCase):
    def python_to_python_via_de_bruijn(self, program):
        program = ParsedAST.parse_python_module(program)
        dfa, s_exp = self.run_canonicalize(program)
        print(ns.render_s_expression(s_exp))
        canonicalized = ParsedAST.from_type_annotated_de_bruijn_ns_s_exp(
            ns.render_s_expression(s_exp), dfa, abstrs=()
        ).to_python()
        return s_exp, canonicalized

    def run_canonicalize(self, program, abstrs=()):
        dfa = export_dfa(abstrs=abstrs)
        s_exp = program.to_type_annotated_de_bruijn_ns_s_exp(
            dfa, "M", de_bruijn_limit=2, abstrs=abstrs
        )
        return dfa, s_exp

    def test_canonicalize_de_bruijn(self):
        program = "x = 2; y = x + 1; z = x + y; x = 3"
        s_exp, canonicalized = self.python_to_python_via_de_bruijn(program)
        expected = """
        (Module~M 
            (/seq~seqS~4
                (Assign~S
                    (list~_L_~1 (Name~L (dbvar-0~Name) (Store~Ctx)))
                    (Constant~E (const-i2~Const) (const-None~ConstKind))
                    (const-None~TC))
                (Assign~S
                    (list~_L_~1 (Name~L (dbvar-0~Name) (Store~Ctx)))
                    (BinOp~E (Name~E (dbvar-1~Name) (Load~Ctx)) (Add~O) (Constant~E (const-i1~Const) (const-None~ConstKind)))
                    (const-None~TC))
                (Assign~S
                    (list~_L_~1 (Name~L (dbvar-0~Name) (Store~Ctx)))
                    (BinOp~E (Name~E (dbvar-2~Name) (Load~Ctx)) (Add~O) (Name~E (dbvar-1~Name) (Load~Ctx)))
                    (const-None~TC))
                (Assign~S
                    (list~_L_~1 (Name~L (dbvar-successor~Name (dbvar-2~Name)) (Store~Ctx)))
                    (Constant~E (const-i3~Const) (const-None~ConstKind))
                    (const-None~TC)))
            (list~_TI_~0))
        """
        self.maxDiff = None
        self.assertEqual(
            ns.render_s_expression(s_exp),
            ns.render_s_expression(ns.parse_s_expression(expected)),
        )

        self.assertEqual(
            canonicalized,
            cwq(
                """
                __0 = 2
                __1 = __0 + 1
                __2 = __0 + __1
                __0 = 3
                """
            ),
        )

    def test_canonicalize_de_bruijn_abstractions(self):
        from .def_use_mask_test import DefUseMaskWithAbstractionsTest

        code = cwq(
            """
            b = 2
            "~(/splice (fn_1 (Name &a:0 Load) &b:0 &a:0))"
            a = a
            """
        )

        t = DefUseMaskWithAbstractionsTest()
        program = t.parse_with_hijacking(code)
        abstrs = [t.abstr_two_assigns]
        dfa, s_exp = self.run_canonicalize(program, abstrs=abstrs)
        expected = """
        (Module~M
            (/seq~seqS~3
                (Assign~S (list~_L_~1 (Name~L (dbvar-0~Name) (Store~Ctx))) (Constant~E (const-i2~Const) (const-None~ConstKind)) (const-None~TC))
                (/splice~S (fn_1~seqS (Name~E (dbvar-1~Name) (Load~Ctx)) (dbvar-1~Name) (dbvar-0~Name)))
                (Assign~S (list~_L_~1 (Name~L (dbvar-2~Name) (Store~Ctx))) (Name~E (dbvar-2~Name) (Load~Ctx)) (const-None~TC)))
                (list~_TI_~0))
        """
        self.assertEqual(
            ns.render_s_expression(s_exp),
            ns.render_s_expression(ns.parse_s_expression(expected)),
        )
        res = (
            ParsedAST.from_type_annotated_de_bruijn_ns_s_exp(
                ns.render_s_expression(s_exp), dfa, abstrs=abstrs
            )
            .abstraction_calls_to_stubs({x.name: x for x in abstrs})
            .to_python()
        )
        self.assertEqual(
            res,
            cwq(
                """
                __0 = 2
                fn_1(__code__('__1'), __ref__(__0), __ref__(__1))
                __1 = __1
                """
            ),
        )

    def assertCanonicalized(self, original, expected):
        _, canonicalized = self.python_to_python_via_de_bruijn(cwq(original))
        self.assertEqual(canonicalized, cwq(expected))

    def test_canonicalize_def(self):
        self.assertCanonicalized(
            """
            def f(x, y, z, k=2): return x + y + z + k
            """,
            """
            def __0(__1, __2, __3, __4=2): return __1 + __2 + __3 + __4
            """,
        )

    @expand_with_slow_tests(1000)
    def test_semantics(self, i):
        eg = small_set_runnable_code_examples()[i]
        from ..extract.rewrite_semantic_test import RewriteSemanticsTest
        from .def_use_mask_test import DefUseMaskTest

        code_original = eg["solution"]
        try:
            check_banned_components(ast.parse(code_original))
        except BannedComponentError:
            return
        se = ns.render_s_expression(
            ParsedAST.parse_python_module(code_original).to_type_annotated_ns_s_exp(
                export_dfa(), "M"
            )
        )
        # Ban internal imports
        if re.search(r"const-&[a-zA-Z0-9_]+:[0-9]+~(Nullable)?NameStr", se):
            return
        try:
            DefUseMaskTest().annotate_program(code_original)
        except AssertionError:
            return
        print(code_original)
        _, canonicalized = self.python_to_python_via_de_bruijn(code_original)
        print(canonicalized)
        # out = outputs(code_original, eg["inputs"][:10])
        # if out is None:
        #     return
        RewriteSemanticsTest().assert_code_same(
            dict(
                inputs=eg["inputs"][:10],
                outputs=eg["outputs"][:10],
            ),
            code_original,
            canonicalized,
            extracted="",
        )


class LikelihoodDeBruijnTest(unittest.TestCase):
    def test_likelihood(self):
        fit_to = ["x = 2; y = x; y = x"]
        # this program is $0 = 2; $0 = $1; $1 = $2
        test_program = "x = 2; y = x; z = y"
        # this program is $0 = 2; $0 = $1; $0 = $1
        # should have a likelihood of
        # (2/3)^3 [$0 on LHS]
        # (1/3)^2 [$1 on RHS]
        # (1/3)^1 [2 on LHS]

        dfa = export_dfa()

        fit_to_prog = [
            ParsedAST.parse_python_module(program).to_type_annotated_de_bruijn_ns_s_exp(
                dfa, "M", de_bruijn_limit=2
            )
            for program in fit_to
        ]
        test_program = ParsedAST.parse_python_module(
            test_program
        ).to_type_annotated_de_bruijn_ns_s_exp(dfa, "M", de_bruijn_limit=2)
        print(test_program)

        dsl = create_dsl(dfa, DSLSubset.from_type_annotated_s_exps(fit_to_prog), "M")
        fam = ns.BigramProgramDistributionFamily(
            dsl,
            additional_preorder_masks=[],  # note: no need if we are using de bruijn
            include_type_preorder_mask=True,
            node_ordering=lambda dist: PythonNodeOrdering(dist, ()),
        )
        counts = fam.count_programs([fit_to_prog])
        dist = fam.counts_to_distribution(counts)[0]

        self.assertEqual(
            Fraction.from_float(
                float(np.exp(fam.compute_likelihood(dist, test_program)))
            ).limit_denominator(1000),
            Fraction(2**3, 3**6),
        )
