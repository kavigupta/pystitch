import unittest
from textwrap import dedent

from permacache import permacache, stable_hash

from imperative_stitch.analyze_program.extract.errors import NotApplicable

from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.compress.run_extraction import convert_output
from imperative_stitch.data.stitch_output_set import load_stitch_output_set
from imperative_stitch.parser.convert import s_exp_to_python
from imperative_stitch.parser.parsed_ast import AbstractionCallAST, ParsedAST
from imperative_stitch.utils.run_code import run_python_with_timeout
from tests.utils import expand_with_slow_tests


def assertSameCode(test, actual, expected):
    actual = dedent(actual).strip()
    print(actual)
    test.assertEqual(
        actual,
        dedent(expected).strip(),
    )


class SequenceTest(unittest.TestCase):
    ctx_in_seq = """
    (Module
        (/seq
            (/splice
                (fn_1 &n:0 &s:0))
            (Assign (list (Name &k:0 Store)) (Call (Attribute (Name &s:0 Load) s_count Load) (list (Constant s_8 None)) nil) None))
        nil)
    """

    ctx_rooted = """
    (Module
        (/seq
            (If
                (Name g_x Load)
                (fn_1 &a:0 &z:0)
                nil))
        nil)
    """

    fn_1_body = """
    (/subseq
        (Assign (list (Name %1 Store)) (Call (Name g_int Load) (list (Call (Name g_input Load) nil nil)) nil) None)
        (Assign (list (Name %2 Store)) (Call (Name g_input Load) nil nil) None))
    """

    fn_1 = Abstraction(
        name="fn_1",
        body=ParsedAST.parse_s_expression(fn_1_body),
        arity=0,
        sym_arity=2,
        choice_arity=0,
        dfa_root="seqS",
        dfa_symvars=["X", "X"],
        dfa_metavars=[],
        dfa_choicevars=[],
    )

    abtractions = {"fn_1": fn_1}

    def test_stub_insertion_subseq(self):
        assertSameCode(
            self,
            ParsedAST.parse_s_expression(self.ctx_in_seq)
            .abstraction_calls_to_stubs(self.abtractions)
            .to_python(),
            """
            fn_1(__ref__(n), __ref__(s))
            k = s.count('8')
            """,
        )

    def test_stub_insertion_rooted(self):
        assertSameCode(
            self,
            ParsedAST.parse_s_expression(self.ctx_rooted)
            .abstraction_calls_to_stubs(self.abtractions)
            .to_python(),
            """
            if x:
                fn_1(__ref__(a), __ref__(z))
            """,
        )

    def test_stub_insertion_rooted_substitute_variables(self):
        parsed = ParsedAST.parse_s_expression(self.ctx_rooted)
        abstracts = parsed.abstraction_calls()
        [handle] = abstracts.keys()
        ac = abstracts[handle]
        new_abstraction_call = AbstractionCallAST(
            tag=ac.tag,
            handle=ac.handle,
            args=[
                ParsedAST.parse_s_expression(x)
                for x in [
                    "&u:0",
                    "&v:0",
                ]
            ],
        )
        parsed = parsed.replace_abstraction_calls({handle: new_abstraction_call})
        assertSameCode(
            self,
            parsed.abstraction_calls_to_stubs(self.abtractions).to_python(),
            """
            if x:
                fn_1(__ref__(u), __ref__(v))
            """,
        )

    def test_injection_subseq(self):
        assertSameCode(
            self,
            ParsedAST.parse_s_expression(self.ctx_in_seq)
            .abstraction_calls_to_bodies(self.abtractions)
            .to_python(),
            """
            n = int(input())
            s = input()
            k = s.count('8')
            """,
        )

    def test_injection_subseq_pragmas(self):
        assertSameCode(
            self,
            ParsedAST.parse_s_expression(self.ctx_in_seq)
            .abstraction_calls_to_bodies(self.abtractions, pragmas=True)
            .to_python(),
            """
            __start_extract__
            n = int(input())
            s = input()
            __end_extract__
            k = s.count('8')
            """,
        )

    def test_injection_rooted(self):
        assertSameCode(
            self,
            ParsedAST.parse_s_expression(self.ctx_rooted)
            .abstraction_calls_to_bodies(self.abtractions)
            .to_python(),
            """
            if x:
                a = int(input())
                z = input()
            """,
        )

    def test_injection_rooted_pragmas(self):
        assertSameCode(
            self,
            ParsedAST.parse_s_expression(self.ctx_rooted)
            .abstraction_calls_to_bodies(self.abtractions, pragmas=True)
            .to_python(),
            """
            if x:
                __start_extract__
                a = int(input())
                z = input()
                __end_extract__
            """,
        )


class MultiKindTest(unittest.TestCase):
    fn_1 = Abstraction(
        name="fn_1",
        body=ParsedAST.parse_s_expression(
            "(/seq (If (BinOp (BinOp (BinOp (BinOp (Constant i1 None) Mult (Constant i2 None)) Mult (Constant i3 None)) Mult (Constant i4 None)) Mult (Constant i5 None)) (/seq (Assign (list (Name %1 Store)) (BinOp (Name %1 Load) Add #0) None) (Assign (list (Name %2 Store)) (List (list (Name g_print Load) (Name g_sum Load) (Name g_u Load)) Load) None) ?0) nil))"
        ),
        arity=1,
        sym_arity=2,
        choice_arity=1,
        dfa_root="seqS",
        dfa_symvars=["X", "X"],
        dfa_metavars=["E"],
        dfa_choicevars=["S"],
    )

    ctx_includes_choicevar = """
    (Module
        (fn_1
            (BinOp (Constant i1 None) Mult (Constant i2 None))
            &x:0
            &y:0
            (Assign (list (Name &z:0 Store)) (Name &x:0 Load) None))
        nil)
    """

    ctx_no_choicevar = """
    (Module
        (fn_1
            (BinOp (Constant i4 None) Mult (Constant i3 None))
            &x:0
            &y:0 
            /nothing)
        nil)
    """

    fn_2 = Abstraction(
        name="fn_2",
        body=ParsedAST.parse_s_expression(
            """
            (If
                (Compare #1 (list Eq) (list (Constant i0 None)))
                (/seq (Expr (Call (Name g_print Load) (list #2) nil)))
                (/seq
                    (If
                        (Compare #1 (list Eq) (list (Constant i1 None)))
                        (/seq (Expr (Call (Name g_print Load) (list #0) nil)))
                        (/seq (Expr (Call (Name g_print Load) (list (Constant i0 None)) nil)))
                    )
                )
            )
            """
        ),
        arity=3,
        sym_arity=0,
        choice_arity=0,
        dfa_root="S",
        dfa_symvars=[],
        dfa_metavars=["E", "E", "E"],
        dfa_choicevars=[],
    )

    ctx_for_fn2_1 = """
    (Module
        (/seq
            (Assign
                (list (Name &n:0 Store))
                (Call (Name g_int Load) (list (Call (Name g_input Load) nil nil)) nil)
                None
            )
            (Assign (list (Name &c:0 Store)) (Call (Name g_input Load) nil nil) None)
            (fn_2
                (Constant i1 None)
                (Call (Attribute (Name &c:0 Load) s_count Load) (list (Constant s_I None)) nil)
                (Call (Attribute (Name &c:0 Load) s_count Load) (list (Constant s_A None)) nil)
            )
        )
        nil
    )
    """

    fn_3 = Abstraction(
        name="fn_3",
        body=ParsedAST.parse_s_expression(
            "(BinOp (BinOp #0 Mult (BinOp #0 Add (Constant i1 None))) FloorDiv (Constant i2 None))"
        ),
        arity=1,
        sym_arity=0,
        choice_arity=0,
        dfa_root="E",
        dfa_metavars=["E"],
        dfa_symvars=[],
        dfa_choicevars=[],
    )

    ctx_for_fn3_1 = """
    (Module
        (/seq
            (Assign
                (list (Name &a:0 Store))
                (Call (Name g_int Load) (list (Call (Name g_input Load) nil nil)) nil)
                None
            )
            (Assign
                (list (Name &b:0 Store))
                (Call (Name g_int Load) (list (Call (Name g_input Load) nil nil)) nil)
                None
            )
            (Assign
                (list (Name &mid:0 Store))
                (BinOp (BinOp (Name &a:0 Load) Add (Name &b:0 Load)) FloorDiv (Constant i2 None))
                None
            )
            (Assign
                (list (Name &a:0 Store))
                (Call (Name g_abs Load) (list (BinOp (Name &mid:0 Load) Sub (Name &a:0 Load))) nil)
                None
            )
            (Assign
                (list (Name &b:0 Store))
                (Call (Name g_abs Load) (list (BinOp (Name &mid:0 Load) Sub (Name &b:0 Load))) nil)
                None
            )
            (Expr
                (Call
                    (Name g_print Load)
                    (list (BinOp (fn_3 (Name &a:0 Load)) Add (fn_3 (Name &b:0 Load))))
                    nil
                )
            )
        )
        nil
    )
    """

    abstractions = {"fn_1": fn_1, "fn_2": fn_2, "fn_3": fn_3}

    def test_stub_includes_choicevar(self):
        assertSameCode(
            self,
            ParsedAST.parse_s_expression(self.ctx_includes_choicevar)
            .abstraction_calls_to_stubs(self.abstractions)
            .to_python(),
            """
            fn_1(__code__('1 * 2'), __ref__(x), __ref__(y), __code__('z = x'))
            """,
        )

    def test_stub_no_choicevar(self):
        assertSameCode(
            self,
            ParsedAST.parse_s_expression(self.ctx_no_choicevar)
            .abstraction_calls_to_stubs(self.abstractions)
            .to_python(),
            """
            fn_1(__code__('4 * 3'), __ref__(x), __ref__(y), None)
            """,
        )

    def test_injection_includes_choicevar(self):
        assertSameCode(
            self,
            ParsedAST.parse_s_expression(self.ctx_includes_choicevar)
            .abstraction_calls_to_bodies(self.abstractions)
            .to_python(),
            """
            if 1 * 2 * 3 * 4 * 5:
                x = x + 1 * 2
                y = [print, sum, u]
                z = x
            """,
        )

    def test_injection_includes_choicevar_pragmas(self):
        assertSameCode(
            self,
            ParsedAST.parse_s_expression(self.ctx_includes_choicevar)
            .abstraction_calls_to_bodies(self.abstractions, pragmas=True)
            .to_python(),
            """
            __start_extract__
            if 1 * 2 * 3 * 4 * 5:
                x = x + {__metavariable__, __m0, 1 * 2}
                y = [print, sum, u]
                __start_choice__
                z = x
                __end_choice__
            __end_extract__
            """,
        )

    def test_injection_doesnt_include_choicevar(self):
        assertSameCode(
            self,
            ParsedAST.parse_s_expression(self.ctx_no_choicevar)
            .abstraction_calls_to_bodies(self.abstractions)
            .to_python(),
            """
            if 1 * 2 * 3 * 4 * 5:
                x = x + 4 * 3
                y = [print, sum, u]
            """,
        )

    def test_stub_fn2_1(self):
        out = (
            ParsedAST.parse_s_expression(self.ctx_for_fn2_1)
            .abstraction_calls_to_stubs(self.abstractions)
            .to_python()
        )
        self.maxDiff = None
        assertSameCode(
            self,
            out,
            r"""
            n = int(input())
            c = input()
            fn_2(__code__('1'), __code__("c.count('I')"), __code__("c.count('A')"))
            """,
        )

    def test_injection_fn2_1(self):
        out = (
            ParsedAST.parse_s_expression(self.ctx_for_fn2_1)
            .abstraction_calls_to_bodies(self.abstractions)
            .to_python()
        )
        self.maxDiff = None
        assertSameCode(
            self,
            out,
            r"""
            n = int(input())
            c = input()
            if c.count('I') == 0:
                print(c.count('A'))
            elif c.count('I') == 1:
                print(1)
            else:
                print(0)
            """,
        )

    def test_injection_fn2_1_pragmas(self):
        out = (
            ParsedAST.parse_s_expression(self.ctx_for_fn2_1)
            .abstraction_calls_to_bodies(self.abstractions, pragmas=True)
            .to_python()
        )
        self.maxDiff = None
        assertSameCode(
            self,
            out,
            r"""
            n = int(input())
            c = input()
            __start_extract__
            if {__metavariable__, __m1, c.count('I')} == 0:
                print({__metavariable__, __m2, c.count('A')})
            elif {__metavariable__, __m1, c.count('I')} == 1:
                print({__metavariable__, __m0, 1})
            else:
                print(0)
            __end_extract__
            """,
        )

    def test_stub_fn3_1(self):
        out = (
            ParsedAST.parse_s_expression(self.ctx_for_fn3_1)
            .abstraction_calls_to_stubs(self.abstractions)
            .to_python()
        )
        self.maxDiff = None
        assertSameCode(
            self,
            out,
            r"""
            a = int(input())
            b = int(input())
            mid = (a + b) // 2
            a = abs(mid - a)
            b = abs(mid - b)
            print(fn_3(__code__('a')) + fn_3(__code__('b')))
            """,
        )

    def test_injection_fn3_1(self):
        out = (
            ParsedAST.parse_s_expression(self.ctx_for_fn3_1)
            .abstraction_calls_to_bodies(self.abstractions)
            .to_python()
        )
        self.maxDiff = None
        assertSameCode(
            self,
            out,
            r"""
            a = int(input())
            b = int(input())
            mid = (a + b) // 2
            a = abs(mid - a)
            b = abs(mid - b)
            print(a * (a + 1) // 2 + b * (b + 1) // 2)
            """,
        )


class RealDataTest(unittest.TestCase):

    @expand_with_slow_tests(len(load_stitch_output_set()))
    def test_realistic_parseable(self, i):
        eg = load_stitch_output_set()[i]
        abstr_dict = eg["abstractions"][0].copy()
        print(abstr_dict)
        abstr_dict["body"] = ParsedAST.parse_s_expression(abstr_dict["body"])
        abstr = dict(fn_1=Abstraction(name="fn_1", **abstr_dict))
        for code, rewritten in zip(eg["code"], eg["rewritten"]):
            code = s_exp_to_python(code)
            ParsedAST.parse_s_expression(rewritten).abstraction_calls_to_stubs(abstr)
            out = (
                ParsedAST.parse_s_expression(rewritten)
                .abstraction_calls_to_bodies(abstr)
                .to_python()
            )
            print("#" * 80)
            print(code)
            print("*" * 80)
            print(out)
            print("#" * 80)
            assertSameCode(
                self,
                out,
                code,
            )
            check_no_crash = (
                ParsedAST.parse_s_expression(rewritten)
                .abstraction_calls_to_bodies(abstr, pragmas=True)
                .to_python()
            )
            self.assertIsNotNone(check_no_crash)

    def currently_invalid(self, abstrs):
        [abstr] = abstrs
        return abstr["dfa_choicevars"]

    @expand_with_slow_tests(len(load_stitch_output_set()))
    def test_realistic_same_behavior(self, i):
        eg = load_stitch_output_set()[i]
        if self.currently_invalid(eg["abstractions"]):
            return
        try:
            abstraction, rewritten = convert_output(eg["abstractions"], eg["rewritten"])
        except NotApplicable:
            # This is fine, we can't rewrite this example
            return
        from .rewrite_semantic_test import RewriteSemanticsTest

        assert len(rewritten) == len(eg["code"])

        for rewr, code_original in zip(rewritten, eg["code"]):
            code_original = s_exp_to_python(code_original)
            print(code_original)
            out = outputs(code_original, eg["inputs"])
            if out is None:
                continue
            RewriteSemanticsTest().assert_code_same(
                dict(
                    inputs=eg["inputs"][:10],
                    outputs=out,
                ),
                code_original,
                rewr,
                extracted=abstraction,
            )


@permacache(
    "imperative_stitch/tests/from_stitch_test/outputs",
    key_function=dict(code=stable_hash, inputs=stable_hash),
)
def outputs(code, inputs):
    result = []
    for inp in inputs:
        out = run_python_with_timeout(code, inp, timeout=1)
        if out is None:
            return None
        result.append(out)
    return result
