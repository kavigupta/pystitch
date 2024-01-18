import unittest
from textwrap import dedent

from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.parser.parsed_ast import ParsedAST


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
