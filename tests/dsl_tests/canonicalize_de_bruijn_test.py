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
from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.parser.parsed_ast import ParsedAST
from imperative_stitch.utils.classify_nodes import export_dfa
from imperative_stitch.utils.def_use_mask.mask import DefUseChainPreorderMask
from imperative_stitch.utils.def_use_mask.ordering import PythonNodeOrdering
from imperative_stitch.utils.export_as_dsl import DSLSubset, create_dsl
from tests.utils import (
    cwq,
    expand_with_slow_tests,
    parse_with_hijacking,
    small_set_runnable_code_examples,
)


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
                    (list~_L_~1 (Name~L (dbvar~Name (dbvar-0~DBV)) (Store~Ctx)))
                    (Constant~E (const-i2~Const) (const-None~ConstKind))
                    (const-None~TC))
                (Assign~S
                    (list~_L_~1 (Name~L (dbvar~Name (dbvar-0~DBV)) (Store~Ctx)))
                    (BinOp~E (Name~E (dbvar~Name (dbvar-1~DBV)) (Load~Ctx)) (Add~O) (Constant~E (const-i1~Const) (const-None~ConstKind)))
                    (const-None~TC))
                (Assign~S
                    (list~_L_~1 (Name~L (dbvar~Name (dbvar-0~DBV)) (Store~Ctx)))
                    (BinOp~E (Name~E (dbvar~Name (dbvar-2~DBV)) (Load~Ctx)) (Add~O) (Name~E (dbvar~Name (dbvar-1~DBV)) (Load~Ctx)))
                    (const-None~TC))
                (Assign~S
                    (list~_L_~1 (Name~L (dbvar~Name (dbvar-successor~DBV (dbvar-2~DBV))) (Store~Ctx)))
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

    def test_canonicalize_de_bruijn_repeated(self):
        program = "x = 2; y = 2; y = x; y = x"
        s_exp, canonicalized = self.python_to_python_via_de_bruijn(program)
        expected = """
        (Module~M
            (/seq~seqS~4
                (Assign~S (list~_L_~1 (Name~L (dbvar~Name (dbvar-0~DBV)) (Store~Ctx))) (Constant~E (const-i2~Const) (const-None~ConstKind)) (const-None~TC))
                (Assign~S (list~_L_~1 (Name~L (dbvar~Name (dbvar-0~DBV)) (Store~Ctx))) (Constant~E (const-i2~Const) (const-None~ConstKind)) (const-None~TC))
                (Assign~S (list~_L_~1 (Name~L (dbvar~Name (dbvar-1~DBV)) (Store~Ctx))) (Name~E (dbvar~Name (dbvar-2~DBV)) (Load~Ctx)) (const-None~TC))
                (Assign~S (list~_L_~1 (Name~L (dbvar~Name (dbvar-1~DBV)) (Store~Ctx))) (Name~E (dbvar~Name (dbvar-2~DBV)) (Load~Ctx)) (const-None~TC)))
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
                __1 = 2
                __1 = __0
                __1 = __0
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
        program = parse_with_hijacking(code)
        abstrs = [t.abstr_two_assigns]
        dfa, s_exp = self.run_canonicalize(program, abstrs=abstrs)
        self.maxDiff = None
        expected = """
        (Module~M
            (/seq~seqS~3
                (Assign~S (list~_L_~1 (Name~L (dbvar~Name (dbvar-0~DBV)) (Store~Ctx))) (Constant~E (const-i2~Const) (const-None~ConstKind)) (const-None~TC))
                (/splice~S (fn_1~seqS (Name~E (dbvar~Name (dbvar-1~DBV)) (Load~Ctx)) (dbvar~Name (dbvar-1~DBV)) (dbvar~Name (dbvar-0~DBV))))
                (Assign~S (list~_L_~1 (Name~L (dbvar~Name (dbvar-1~DBV)) (Store~Ctx))) (Name~E (dbvar~Name (dbvar-1~DBV)) (Load~Ctx)) (const-None~TC)))
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

        code_original = eg["solution"]
        se = parse_and_check(code_original)
        if se is None:
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

    def compute_likelihood(
        self,
        fit_to,
        test_program,
        de_bruijn_limit=2,
        abstrs=(),
        parser=ParsedAST.parse_python_module,
    ):
        dfa = export_dfa(abstrs=abstrs)

        fit_to_prog = [parser(program) for program in fit_to]
        fit_to_prog = [
            x.to_type_annotated_de_bruijn_ns_s_exp(
                dfa, "M", de_bruijn_limit=de_bruijn_limit, abstrs=abstrs
            )
            for x in fit_to_prog
        ]
        print(ns.render_s_expression(fit_to_prog[0]))
        test_program = parser(test_program).to_type_annotated_de_bruijn_ns_s_exp(
            dfa, "M", de_bruijn_limit=de_bruijn_limit, abstrs=abstrs
        )
        print(ns.render_s_expression(test_program))

        dsl = create_dsl(
            dfa,
            DSLSubset.from_program(
                dfa,
                *fit_to_prog,
                root="M",
                abstrs=abstrs,
                to_s_exp=lambda program, dfa, root_sym: (
                    program.to_type_annotated_de_bruijn_ns_s_exp(
                        dfa, root_sym, de_bruijn_limit=de_bruijn_limit, abstrs=abstrs
                    )
                    if not isinstance(program, ns.SExpression)
                    else program
                ),
            ),
            "M",
        )
        fam = ns.BigramProgramDistributionFamily(
            dsl,
            additional_preorder_masks=[
                lambda dist, dsl: DefUseChainPreorderMask(
                    dist, dsl, dfa=dfa, abstrs=abstrs
                )
            ],  # note: no need if we are using de bruijn
            include_type_preorder_mask=True,
            node_ordering=lambda dist: PythonNodeOrdering(dist, abstrs),
        )
        counts = fam.count_programs([fit_to_prog])
        dist = fam.counts_to_distribution(counts)[0]

        probs_each = fam.compute_likelihood_per_node(dist, test_program)
        print(probs_each)
        results = [
            (
                ns.render_s_expression(x),
                Fraction.from_float(float(np.exp(y))).limit_denominator(),
            )
            for x, y in probs_each
            if y != 0  # remove zero log-likelihoods
        ]

        print(results)

        return results

    def test_likelihood_more_variables(self):
        fit_to = ["x = 2; y = x; y = x"]
        # this program is $0 = 2; $0 = $1; $1 = $2
        test_program = "x = 2; y = x; z = y"
        # this program is $0 = 2; $0 = $1; $0 = $1
        # should have a likelihood of
        # (2/3)^3 [$0 on LHS]
        # (1/3)^2 [$1 on RHS]
        # (1/3)^1 [2 on LHS]

        self.assertEqual(
            self.compute_likelihood(fit_to, test_program),
            [
                # this is the second $0 =. This is 1/2 since it either is $0 or $1, which are equally likely
                # in the original program (2 and 2)
                ("(dbvar-0~DBV)", Fraction(1, 2)),
                # this is the first = $1. This is 2/3 since there's a 2/3 chance of picking a variable on the RHS
                ("(Name~E (dbvar~Name (dbvar-1~DBV)) (Load~Ctx))", Fraction(2, 3)),
                # this is the second $0 =. This is 2/5 since it's either $0=, $1=, or $2=, and $0 appears 2/5 times
                # a variable appears in the original program
                ("(dbvar-0~DBV)", Fraction(2, 5)),
                # same as above
                ("(Name~E (dbvar~Name (dbvar-1~DBV)) (Load~Ctx))", Fraction(2, 3)),
                # this is the second = $1. The first was 1 since there was no other variable. This is 2/3 since
                # $1 appears twice and $2 appears once in the original program
                ("(dbvar-1~DBV)", Fraction(2, 3)),
            ],
        )

    def test_likelihood_more_lookback_zero(self):
        fit_to = ["x = 2; y = 2; y = x; y = x"]
        # this program is $0 = 2; $0 = 2; $1 = $2; $1 = $2
        test_program = "x = 2; y = x; z = y; z = x"
        # this program is $0 = 2; $0 = $1; $0 = $1; $1 = $3
        # should have a likelihood of 0 because the successor node doesn't appear in the original

        self.assertEqual(
            self.compute_likelihood(fit_to, test_program),
            [
                ("(dbvar-0~DBV)", Fraction(1, 2)),
                ("(Name~E (dbvar~Name (dbvar-1~DBV)) (Load~Ctx))", Fraction(1, 2)),
                ("(dbvar-0~DBV)", Fraction(1, 3)),
                ("(Name~E (dbvar~Name (dbvar-1~DBV)) (Load~Ctx))", Fraction(1, 2)),
                ("(dbvar-1~DBV)", Fraction(1, 2)),
                ("(dbvar-1~DBV)", Fraction(1, 3)),
                (
                    "(Name~E (dbvar~Name (dbvar-successor~DBV (dbvar-2~DBV))) (Load~Ctx))",
                    Fraction(1, 2),
                ),
                ("(dbvar-successor~DBV (dbvar-2~DBV))", Fraction(0, 1)),
                ("(dbvar-2~DBV)", Fraction(0, 1)),
            ],
        )

    def test_likelihood_more_lookback_nonzero_dblimit_0(self):
        fit_to = ["x = 2; y = 2; y = x; y = x"]
        test_program = "x = 2; y = x; z = y; z = x"
        # should be possible, unlike the previous test, because the de bruijn limit is 0

        self.assertEqual(
            self.compute_likelihood(fit_to, test_program, de_bruijn_limit=0),
            [
                ("(dbvar-0~DBV)", Fraction(1, 3)),
                (
                    "(Name~E (dbvar~Name (dbvar-successor~DBV (dbvar-0~DBV))) (Load~Ctx))",
                    Fraction(1, 2),
                ),
                ("(dbvar-0~DBV)", Fraction(2, 3)),
                ("(dbvar-0~DBV)", Fraction(1, 3)),
                (
                    "(Name~E (dbvar~Name (dbvar-successor~DBV (dbvar-0~DBV))) (Load~Ctx))",
                    Fraction(1, 2),
                ),
                ("(dbvar-0~DBV)", Fraction(2, 3)),
                ("(dbvar-successor~DBV (dbvar-0~DBV))", Fraction(2, 3)),
                ("(dbvar-0~DBV)", Fraction(2, 3)),
                (
                    "(Name~E (dbvar~Name (dbvar-successor~DBV (dbvar-successor~DBV (dbvar-successor~DBV (dbvar-0~DBV))))) (Load~Ctx))",
                    Fraction(1, 2),
                ),
                (
                    "(dbvar-successor~DBV (dbvar-successor~DBV (dbvar-0~DBV)))",
                    Fraction(1, 3),
                ),
                ("(dbvar-successor~DBV (dbvar-0~DBV))", Fraction(1, 3)),
                ("(dbvar-0~DBV)", Fraction(2, 3)),
            ],
        )

    def test_likelihood_more_lookback_nonzero(self):
        fit_to = ["x = 2; y = x; z = x; a = x; y = a; x = a"]
        test_program = "x = 2; y = x; z = x; a = x; b = x; c = x"
        # way more variables, and way more lookback

        self.assertEqual(
            self.compute_likelihood(fit_to, test_program),
            [
                ("(dbvar-0~DBV)", Fraction(4, 7)),
                ("(Name~E (dbvar~Name (dbvar-1~DBV)) (Load~Ctx))", Fraction(5, 6)),
                ("(dbvar-0~DBV)", Fraction(1, 2)),
                ("(Name~E (dbvar~Name (dbvar-2~DBV)) (Load~Ctx))", Fraction(5, 6)),
                ("(dbvar-2~DBV)", Fraction(1, 4)),
                ("(dbvar-0~DBV)", Fraction(4, 11)),
                (
                    "(Name~E (dbvar~Name (dbvar-successor~DBV (dbvar-2~DBV))) (Load~Ctx))",
                    Fraction(5, 6),
                ),
                ("(dbvar-successor~DBV (dbvar-2~DBV))", Fraction(3, 7)),
                ("(dbvar-2~DBV)", Fraction(3, 4)),
                ("(dbvar-0~DBV)", Fraction(4, 11)),
                (
                    "(Name~E (dbvar~Name (dbvar-successor~DBV (dbvar-successor~DBV (dbvar-2~DBV)))) (Load~Ctx))",
                    Fraction(5, 6),
                ),
                (
                    "(dbvar-successor~DBV (dbvar-successor~DBV (dbvar-2~DBV)))",
                    Fraction(3, 7),
                ),
                ("(dbvar-successor~DBV (dbvar-2~DBV))", Fraction(1, 4)),
                ("(dbvar-2~DBV)", Fraction(3, 4)),
                ("(dbvar-0~DBV)", Fraction(4, 11)),
                (
                    "(Name~E (dbvar~Name (dbvar-successor~DBV (dbvar-successor~DBV (dbvar-successor~DBV (dbvar-2~DBV))))) (Load~Ctx))",
                    Fraction(5, 6),
                ),
                (
                    "(dbvar-successor~DBV (dbvar-successor~DBV (dbvar-successor~DBV (dbvar-2~DBV))))",
                    Fraction(3, 7),
                ),
                (
                    "(dbvar-successor~DBV (dbvar-successor~DBV (dbvar-2~DBV)))",
                    Fraction(1, 4),
                ),
                ("(dbvar-successor~DBV (dbvar-2~DBV))", Fraction(1, 4)),
                ("(dbvar-2~DBV)", Fraction(3, 4)),
            ],
        )

    @expand_with_slow_tests(1000)
    def test_no_crash(self, i):
        eg = small_set_runnable_code_examples()[i]
        code_original = eg["solution"]
        se = parse_and_check(code_original)
        if se is None:
            return
        self.compute_likelihood([code_original], code_original)


def parse_and_check(code_original):
    from .def_use_mask_test import DefUseMaskTest

    try:
        check_banned_components(ast.parse(code_original))
    except BannedComponentError:
        return None
    se = ns.render_s_expression(
        ParsedAST.parse_python_module(code_original).to_type_annotated_ns_s_exp(
            export_dfa(), "M"
        )
    )
    # Ban internal imports
    if re.search(r"const-&[a-zA-Z0-9_]+:[0-9]+~(Nullable)?NameStr", se):
        return None
    try:
        DefUseMaskTest().annotate_program(code_original)
    except AssertionError:
        return None
    return se
