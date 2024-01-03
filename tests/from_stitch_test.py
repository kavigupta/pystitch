import unittest
from textwrap import dedent

from imperative_stitch.compress.abstraction import Abstraction, handle_abstractions
from imperative_stitch.to_s import s_exp_to_python


def assertSameCode(test, actual, expected):
    test.assertEqual(
        dedent(actual).strip(),
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
        body=fn_1_body,
        arity=0,
        sym_arity=2,
        choice_arity=0,
        dfa_root="S",
        dfa_symvars=["X", "X"],
        dfa_metavars=[],
        dfa_choicevars=[],
    )

    def test_default_insertion_subseq(self):
        assertSameCode(
            self,
            s_exp_to_python(self.ctx_in_seq),
            """
            fn_1(n, s)
            k = s.count('8')
            """,
        )

    def test_default_insertion_rooted(self):
        assertSameCode(
            self,
            s_exp_to_python(self.ctx_rooted),
            """
            if x:
                fn_1(a, z)
            """,
        )

    def test_injection_subseq(self):
        assertSameCode(
            self,
            s_exp_to_python(self.ctx_in_seq, handle_abstractions({"fn_1": self.fn_1})),
            """
            n = int(input())
            s = input()
            k = s.count('8')
            """,
        )

    def test_injection_rooted(self):
        assertSameCode(
            self,
            s_exp_to_python(self.ctx_rooted, handle_abstractions({"fn_1": self.fn_1})),
            """
            if x:
                a = int(input())
                z = input()
            """,
        )


class MultiKindTest(unittest.TestCase):
    fn_1 = Abstraction(
        body="(/seq (If (BinOp (BinOp (BinOp (BinOp (Constant i1 None) Mult (Constant i2 None)) Mult (Constant i3 None)) Mult (Constant i4 None)) Mult (Constant i5 None)) (/seq (Assign (list (Name %1 Store)) (BinOp (Name %1 Load) Add #0) None) (Assign (list (Name %2 Store)) (List (list (Name g_print Load) (Name g_sum Load) (Name g_u Load)) Load) None) ?0) nil))",
        arity=1,
        sym_arity=2,
        choice_arity=1,
        dfa_root="S",
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

    def test_stub_includes_choicevar(self):
        assertSameCode(
            self,
            s_exp_to_python(self.ctx_includes_choicevar),
            """
            fn_1(1 * 2, x, y, __code__("z = x"))
            """,
        )

    def test_stub_no_choicevar(self):
        assertSameCode(
            self,
            s_exp_to_python(self.ctx_no_choicevar),
            """
            fn_1(4 * 3, x, y, __no_code__)
            """,
        )

    def test_injection_includes_choicevar(self):
        assertSameCode(
            self,
            s_exp_to_python(
                self.ctx_includes_choicevar, handle_abstractions({"fn_1": self.fn_1})
            ),
            """
            x = 1 * 2
            y = x
            z = x
            """,
        )


# TODO add test: abstraction with symvar, metavariable, choice variable


# TODO add test: abstraction rooted at an Expr node
