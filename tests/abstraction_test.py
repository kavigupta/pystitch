import unittest
from textwrap import dedent

from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.to_s import s_exp_to_list_s_expression


def assertSameCode(test, actual, expected):
    test.assertEqual(
        dedent(actual).strip(),
        dedent(expected).strip(),
    )


class AbstractionTest(unittest.TestCase):
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

    def test_basic_stub_rendering(self):
        stub = self.fn_1.render_stub(
            [s_exp_to_list_s_expression(x) for x in ["&a:0", "&z:0"]]
        )

        print(stub)
        1/0