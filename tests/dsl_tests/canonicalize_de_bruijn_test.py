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
    def compute_likelihood(self, fit_to, test_program):
        dfa = export_dfa()

        fit_to_prog = [
            ParsedAST.parse_python_module(program).to_type_annotated_de_bruijn_ns_s_exp(
                dfa, "M", de_bruijn_limit=2
            )
            for program in fit_to
        ]
        print(ns.render_s_expression(fit_to_prog[0]))
        test_program = ParsedAST.parse_python_module(
            test_program
        ).to_type_annotated_de_bruijn_ns_s_exp(dfa, "M", de_bruijn_limit=2)
        print(ns.render_s_expression(test_program))

        dsl = create_dsl(dfa, DSLSubset.from_type_annotated_s_exps(fit_to_prog), "M")
        fam = ns.BigramProgramDistributionFamily(
            dsl,
            additional_preorder_masks=[
                lambda dist, dsl: DefUseChainPreorderMask(
                    dist, dsl, dfa=dfa, abstrs=(), de_bruijn_limit=2
                )
            ],  # note: no need if we are using de bruijn
            include_type_preorder_mask=True,
            node_ordering=lambda dist: PythonNodeOrdering(dist, ()),
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
                ("(dbvar-0~DBV)", Fraction(1, 2)),
                ("(Name~E (dbvar~Name (dbvar-1~DBV)) (Load~Ctx))", Fraction(1, 2)),
                ("(dbvar-1~DBV)", Fraction(1, 2)),
                (
                    "(Name~E (dbvar~Name (dbvar-successor~DBV (dbvar-2~DBV))) (Load~Ctx))",
                    Fraction(1, 2),
                ),
                ("(dbvar-successor~DBV (dbvar-2~DBV))", Fraction(0, 1)),
                ("(dbvar-2~DBV)", Fraction(0, 1)),
            ],
        )

    def test_likelihood_more_lookback_nonzero(self):
        fit_to = ["x = 2; y = x; z = x; a = x; y = a; x = a"]
        # this program is $0 = 2; $0 = 2; $1 = $2; $1 = $2
        test_program = "x = 2; y = x; z = x; a = x; y = a; x = a"
        # this program is $0 = 2; $0 = $1; $0 = $1; $1 = $3
        # should have a likelihood of 0 because the successor node doesn't appear in the original

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
                ("(dbvar-successor~DBV (dbvar-2~DBV))", Fraction(3, 11)),
                ("(dbvar-2~DBV)", Fraction(3, 4)),
                ("(Name~E (dbvar~Name (dbvar-1~DBV)) (Load~Ctx))", Fraction(5, 6)),
                ("(dbvar-1~DBV)", Fraction(3, 7)),
                (
                    "(dbvar-successor~DBV (dbvar-successor~DBV (dbvar-2~DBV)))",
                    Fraction(3, 11),
                ),
                ("(dbvar-successor~DBV (dbvar-2~DBV))", Fraction(1, 4)),
                ("(dbvar-2~DBV)", Fraction(3, 4)),
                ("(Name~E (dbvar~Name (dbvar-1~DBV)) (Load~Ctx))", Fraction(5, 6)),
                ("(dbvar-1~DBV)", Fraction(3, 7)),
            ],
        )
        1 / 0

    def test_2(self):
        import json
        import neurosym as ns

        from imperative_stitch.parser import ParsedAST
        from imperative_stitch.compress.abstraction import Abstraction
        from imperative_stitch.utils.export_as_dsl import DSLSubset, create_dsl
        from imperative_stitch.utils.def_use_mask.ordering import PythonNodeOrdering

        programs = [
            "(Module (/seq (Assign (list (Name &MOD:0 Store)) (Constant i1000000007 None) None) (Assign (list (Tuple (list (_starred_content (Name &n:0 Store)) (_starred_content (Name &k:0 Store))) Store)) (Call (Name g_map Load) (list (_starred_content (Name g_int Load)) (_starred_content (Call (Attribute (Call (Name g_input Load) nil nil) s_split Load) nil nil))) nil) None) (Assign (list (Name &segments:0 Store)) (List nil Load) None) (Assign (list (Name &points:0 Store)) (List nil Load) None) (For (Name &_:0 Store) (Call (Name g_range Load) (list (_starred_content (Name &n:0 Load))) nil) (/seq (fn_1 &r:0 &l:0) (Expr (Call (Attribute (Name &segments:0 Load) s_append Load) (list (_starred_content (Tuple (list (_starred_content (Name &l:0 Load)) (_starred_content (Name &r:0 Load))) Load))) nil)) (/splice (/choiceseq (Expr (Call (Attribute (Name &points:0 Load) s_append Load) (list (_starred_content (Tuple (list (_starred_content (Name &l:0 Load)) (_starred_content (Constant i1 None))) Load))) nil)) (Expr (Call (Attribute (Name &points:0 Load) s_append Load) (list (_starred_content (Tuple (list (_starred_content (BinOp (Name &r:0 Load) Add (Constant i1 None))) (_starred_content (UnaryOp USub (Constant i1 None)))) Load))) nil))))) (/seq) None) (Expr (Call (Attribute (Name &points:0 Load) s_sort Load) nil nil)) (Assign (list (Name &current:0 Store)) (Constant i0 None) None) (Assign (list (Name &contribution:0 Store)) (BinOp (List (list (_starred_content (Constant i0 None))) Load) Mult (Name &n:0 Load)) None) (For (Name &i:0 Store) (Call (Name g_range Load) (list (_starred_content (Constant i1 None)) (_starred_content (Call (Name g_len Load) (list (_starred_content (Name &points:0 Load))) nil))) nil) (/seq (AugAssign (Name &current:0 Store) Add (Subscript (fn_4 (Name &i:0 Load) &points:0) (_slice_content (Constant i1 None)) Load)) (AugAssign (Subscript (Name &contribution:0 Load) (_slice_content (BinOp (Name &current:0 Load) Sub (Constant i1 None))) Store) Add (BinOp (Subscript (fn_5 &i:0 &points:0) (_slice_content (Constant i0 None)) Load) Sub (Subscript (fn_4 (Name &i:0 Load) &points:0) (_slice_content (Constant i0 None)) Load)))) (/seq) None) (Assign (list (Name &pre_sum:0 Store)) (BinOp (List (list (_starred_content (Constant i0 None))) Load) Mult (Name &n:0 Load)) None) (Assign (list (Subscript (Name &pre_sum:0 Load) (_slice_content (Constant i0 None)) Store)) (Subscript (Name &contribution:0 Load) (_slice_content (Constant i0 None)) Load) None) (/splice (/subseq (For (Name &i:0 Store) (Call (Name g_range Load) (list (_starred_content (Constant i1 None)) (_starred_content (Name &n:0 Load))) nil) (/seq (Assign (list (Subscript (Name &pre_sum:0 Load) (_slice_content (Name &i:0 Load)) Store)) (BinOp (Subscript (Name &pre_sum:0 Load) (_slice_content (BinOp (Name &i:0 Load) Sub (Constant i1 None))) Load) Add (fn_5 &i:0 &contribution:0)) None)) (/seq) None) (Assign (list (Name &answer:0 Store)) (Constant i0 None) None))) (For (Name &i:0 Store) (Call (Name g_range Load) (list (_starred_content (Name &n:0 Load))) nil) (/seq (If (Compare (Name &i:0 Load) (list GtE) (list (BinOp (Name &k:0 Load) Sub (Constant i1 None)))) (/seq (AugAssign (Name &answer:0 Store) Add (BinOp (BinOp (Subscript (Name &contribution:0 Load) (_slice_content (Name &i:0 Load)) Load) Mult (Subscript (Name &pre_sum:0 Load) (_slice_content (BinOp (BinOp (Name &i:0 Load) Sub (Name &k:0 Load)) Add (Constant i1 None))) Load)) Mod (Name &MOD:0 Load)))) (/seq))) (/seq) None) (Expr (Call (Name g_print Load) (list (_starred_content (BinOp (Name &answer:0 Load) Mod (Name &MOD:0 Load)))) nil))) nil)"
        ]

        dfa = {
            "M": {"Module": ["seqS", "[TI]"]},
            "S": {
                "AnnAssign": ["L", "TA", "E", "bool"],
                "Assert": ["E", "E"],
                "Assign": ["[L]", "E", "TC"],
                "AsyncFor": ["L", "E", "seqS", "seqS", "TC"],
                "AsyncFunctionDef": ["Name", "As", "seqS", "[E]", "TA", "TC"],
                "AsyncWith": ["[W]", "seqS", "TC"],
                "AugAssign": ["L", "O", "E"],
                "ClassDef": ["Name", "[E]", "[K]", "seqS", "[E]"],
                "Delete": ["[L]"],
                "Expr": ["E"],
                "For": ["L", "E", "seqS", "seqS", "TC"],
                "FunctionDef": ["Name", "As", "seqS", "[E]", "TA", "TC"],
                "Global": ["[NameStr]"],
                "If": ["E", "seqS", "seqS"],
                "Import": ["[alias]"],
                "ImportFrom": ["NullableNameStr", "[alias]", "int"],
                "Nonlocal": ["[NameStr]"],
                "Raise": ["E", "E"],
                "Return": ["E"],
                "Try": ["seqS", "[EH]", "seqS", "seqS"],
                "While": ["E", "seqS", "seqS"],
                "With": ["[W]", "seqS", "TC"],
                "/splice": ["seqS"],
                "fn_1": ["Name", "Name"],
                "fn_6": ["Name", "Name"],
                "fn_7": ["Name", "Name", "Name", "Name", "Name", "seqS"],
                "fn_10": ["Name"],
                "fn_13": ["E"],
                "fn_15": ["E", "Name", "Name"],
            },
            "E": {
                "Attribute": ["E", "NameStr", "Ctx"],
                "Await": ["E"],
                "BinOp": ["E", "O", "E"],
                "BoolOp": ["O", "[E]"],
                "Call": ["E", "[StarredRoot]", "[K]"],
                "Compare": ["E", "[O]", "[E]"],
                "Constant": ["Const", "ConstKind"],
                "Dict": ["[E]", "[E]"],
                "DictComp": ["E", "E", "[C]"],
                "GeneratorExp": ["E", "[C]"],
                "IfExp": ["E", "E", "E"],
                "JoinedStr": ["[F]"],
                "Lambda": ["As", "E"],
                "List": ["[StarredRoot]", "Ctx"],
                "ListComp": ["E", "[C]"],
                "Name": ["Name", "Ctx"],
                "NamedExpr": ["L", "E"],
                "Set": ["[StarredRoot]"],
                "SetComp": ["E", "[C]"],
                "Starred": ["E", "Ctx"],
                "Subscript": ["E", "SliceRoot", "Ctx"],
                "Tuple": ["[StarredRoot]", "Ctx"],
                "UnaryOp": ["O", "E"],
                "Yield": ["E"],
                "YieldFrom": ["E"],
                "fn_3": ["Name", "Name"],
                "fn_4": ["E", "Name"],
                "fn_5": ["Name", "Name"],
                "fn_9": ["E"],
                "fn_11": ["E"],
                "fn_12": ["E"],
                "fn_14": ["E"],
                "fn_param_1": [],
                "fn_param_2": ["E"],
                "fn_param_3": ["E"],
                "fn_param_4": [],
                "fn_param_5": [],
                "fn_param_6": [],
                "fn_param_7": [],
                "fn_param_8": [],
                "fn_param_9": ["E"],
                "fn_param_11": ["E", "E"],
                "fn_param_13": [],
                "fn_param_14": ["E", "E"],
                "fn_param_15": [],
                "fn_param_16": ["E"],
                "fn_param_17": [],
                "fn_param_18": [],
                "fn_param_19": [],
                "fn_param_20": ["E", "E", "E", "E"],
                "fn_param_21": [],
                "fn_param_22": [],
            },
            "SliceRoot": {
                "_slice_content": ["E"],
                "_slice_slice": ["Slice"],
                "_slice_tuple": ["SliceTuple"],
            },
            "SliceTuple": {"Tuple": ["[SliceRoot]", "Ctx"]},
            "[SliceRoot]": {"list": ["SliceRoot"]},
            "StarredRoot": {"_starred_content": ["E"], "_starred_starred": ["Starred"]},
            "Starred": {"Starred": ["E", "Ctx"]},
            "Slice": {"Slice": ["E", "E", "E"]},
            "As": {"arguments": ["[A]", "[A]", "A", "[A]", "[E]", "A", "[E]"]},
            "A": {"arg": ["Name", "TA", "TC"]},
            "F": {
                "Constant": ["F", "F"],
                "FormattedValue": ["E", "int", "F"],
                "JoinedStr": ["[F]"],
            },
            "C": {"comprehension": ["L", "E", "[E]", "bool"]},
            "K": {"keyword": ["NullableNameStr", "E"]},
            "EH": {"ExceptHandler": ["E", "NullableName", "seqS"]},
            "W": {"withitem": ["E", "L"]},
            "L": {
                "Attribute": ["E", "NameStr", "Ctx"],
                "List": ["[L]", "Ctx"],
                "Name": ["Name", "Ctx"],
                "Starred": ["L", "Ctx"],
                "Subscript": ["E", "SliceRoot", "Ctx"],
                "Tuple": ["[L]", "Ctx"],
                "_starred_content": ["L"],
                "_starred_starred": ["L"],
            },
            "seqS": {
                "/seq": ["S"],
                "/subseq": ["S"],
                "/choiceseq": ["S"],
                "fn_2": ["E", "Name", "Name", "Name", "Name"],
                "fn_8": ["Name", "Name", "seqS"],
                "fn_param_0": [],
                "fn_param_10": [],
                "fn_param_12": ["E", "E", "E", "E", "E", "S", "S", "S", "seqS"],
            },
            "[E]": {"list": ["E"]},
            "[StarredRoot]": {"list": ["StarredRoot"]},
            "alias": {"alias": ["NameStr", "NullableNameStr"]},
            "[NameStr]": {"list": ["NameStr"]},
            "TA": {
                "AST": [],
                "Add": [],
                "And": [],
                "AnnAssign": ["TA", "TA", "TA", "TA"],
                "Assert": ["TA", "TA"],
                "Assign": ["TA", "TA", "TA"],
                "AsyncFor": ["TA", "TA", "TA", "TA", "TA"],
                "AsyncFunctionDef": ["TA", "TA", "TA", "TA", "TA", "TA"],
                "AsyncWith": ["TA", "TA", "TA"],
                "Attribute": ["TA", "TA", "TA"],
                "AugAssign": ["TA", "TA", "TA"],
                "AugLoad": [],
                "AugStore": [],
                "Await": ["TA"],
                "BinOp": ["TA", "TA", "TA"],
                "BitAnd": [],
                "BitOr": [],
                "BitXor": [],
                "BoolOp": ["TA", "TA"],
                "Break": [],
                "Bytes": ["TA"],
                "Call": ["TA", "TA", "TA"],
                "ClassDef": ["TA", "TA", "TA", "TA", "TA"],
                "Compare": ["TA", "TA", "TA"],
                "Constant": ["TA", "TA"],
                "Continue": [],
                "Del": [],
                "Delete": ["TA"],
                "Dict": ["TA", "TA"],
                "DictComp": ["TA", "TA", "TA"],
                "Div": [],
                "Ellipsis": [],
                "Eq": [],
                "ExceptHandler": ["TA", "TA", "TA"],
                "Expr": ["TA"],
                "Expression": ["TA"],
                "ExtSlice": [],
                "FloorDiv": [],
                "For": ["TA", "TA", "TA", "TA", "TA"],
                "FormattedValue": ["TA", "TA", "TA"],
                "FunctionDef": ["TA", "TA", "TA", "TA", "TA", "TA"],
                "FunctionType": ["TA", "TA"],
                "GeneratorExp": ["TA", "TA"],
                "Global": ["TA"],
                "Gt": [],
                "GtE": [],
                "If": ["TA", "TA", "TA"],
                "IfExp": ["TA", "TA", "TA"],
                "Import": ["TA"],
                "ImportFrom": ["TA", "TA", "TA"],
                "In": [],
                "Index": [],
                "Interactive": ["TA"],
                "Invert": [],
                "Is": [],
                "IsNot": [],
                "JoinedStr": ["TA"],
                "LShift": [],
                "Lambda": ["TA", "TA"],
                "List": ["TA", "TA"],
                "ListComp": ["TA", "TA"],
                "Load": [],
                "Lt": [],
                "LtE": [],
                "MatMult": [],
                "Mod": [],
                "Module": ["TA", "TA"],
                "Mult": [],
                "Name": ["TA", "TA"],
                "NameConstant": ["TA", "TA"],
                "NamedExpr": ["TA", "TA"],
                "Nonlocal": ["TA"],
                "Not": [],
                "NotEq": [],
                "NotIn": [],
                "Num": ["TA"],
                "Or": [],
                "Param": [],
                "Pass": [],
                "Pow": [],
                "RShift": [],
                "Raise": ["TA", "TA"],
                "Return": ["TA"],
                "Set": ["TA"],
                "SetComp": ["TA", "TA"],
                "Slice": ["TA", "TA", "TA"],
                "Starred": ["TA", "TA"],
                "Store": [],
                "Str": ["TA"],
                "Sub": [],
                "Subscript": ["TA", "TA", "TA"],
                "Suite": [],
                "Try": ["TA", "TA", "TA", "TA"],
                "Tuple": ["TA", "TA"],
                "TypeIgnore": ["TA", "TA"],
                "UAdd": [],
                "USub": [],
                "UnaryOp": ["TA", "TA"],
                "While": ["TA", "TA", "TA"],
                "With": ["TA", "TA", "TA"],
                "Yield": ["TA"],
                "YieldFrom": ["TA"],
                "alias": ["TA", "TA"],
                "arg": ["TA", "TA", "TA"],
                "arguments": ["TA", "TA", "TA", "TA", "TA", "TA", "TA"],
                "boolop": [],
                "cmpop": [],
                "comprehension": ["TA", "TA", "TA", "TA"],
                "excepthandler": [],
                "expr": [],
                "expr_context": [],
                "keyword": ["TA", "TA"],
                "mod": [],
                "operator": [],
                "slice": [],
                "stmt": [],
                "type_ignore": [],
                "unaryop": [],
                "withitem": ["TA", "TA"],
                "_slice_content": ["TA"],
                "_slice_slice": ["TA"],
                "_slice_tuple": ["TA"],
                "_starred_content": ["TA"],
                "_starred_starred": ["TA"],
                "list": ["TA"],
            },
            "[F]": {"list": ["F"]},
            "[A]": {"list": ["A"]},
            "[C]": {"list": ["C"]},
            "[EH]": {"list": ["EH"]},
            "[K]": {"list": ["K"]},
            "[L]": {"list": ["L"]},
            "[O]": {"list": ["O"]},
            "[W]": {"list": ["W"]},
            "[alias]": {"list": ["alias"]},
            "[TI]": {"list": ["TI"]},
        }

        absts = json.load(open("/home/kavi/Downloads/tmp-abstractions-test-file.json"))
        absts = [Abstraction.of(**entry) for entry in absts]

        parsed_asts = [ParsedAST.parse_s_expression(p) for p in programs]
        programs_to_count = [
            p.to_type_annotated_de_bruijn_ns_s_exp(
                dfa,
                "M",
                de_bruijn_limit=2,
                abstrs=absts,
            )
            for p in parsed_asts
        ]

        dsl = create_dsl(
            dfa, DSLSubset.from_type_annotated_s_exps(programs_to_count), "M"
        )
        fam = ns.BigramProgramDistributionFamily(
            dsl,
            additional_preorder_masks=[],  # note: no need if we are using de bruijn
            include_type_preorder_mask=True,
            node_ordering=lambda dist: PythonNodeOrdering(dist, ()),
        )

        counts = fam.count_programs([programs_to_count])
