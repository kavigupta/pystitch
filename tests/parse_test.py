import ast
import unittest

import neurosym as ns

from imperative_stitch.parser import ParsedAST, python_to_s_exp, s_exp_to_python
from imperative_stitch.utils.recursion import no_recursionlimit
from tests.abstraction_test import assertSameCode

from .utils import expand_with_slow_tests, small_set_examples


class ParseUnparseInverseTest(unittest.TestCase):
    def canonicalize(self, python_code):
        return ast.unparse(ast.parse(python_code))

    def assert_valid_s_exp(self, s_exp, no_leaves):
        if not isinstance(s_exp, ns.SExpression):
            assert isinstance(s_exp, str)
            if no_leaves:
                self.fail(f"leaf: {s_exp}")
            return
        if s_exp.symbol not in {"/seq"}:
            self.assertTrue(isinstance(s_exp.symbol, str), repr(s_exp.symbol))
            if not no_leaves:
                self.assertTrue(len(s_exp.children) >= 1, repr(s_exp))
        for y in s_exp.children:
            self.assert_valid_s_exp(y, no_leaves)

    def check_with_args(self, test_code, no_leaves=False):

        test_code = self.canonicalize(test_code)
        s_exp = python_to_s_exp(
            test_code, renderer_kwargs=dict(columns=80), no_leaves=no_leaves
        )
        with no_recursionlimit():
            self.assert_valid_s_exp(ns.parse_s_expression(s_exp), no_leaves=no_leaves)
        s_exp_parsed = ParsedAST.parse_s_expression(s_exp)
        print(repr(s_exp_parsed))
        modified = s_exp_to_python(s_exp)
        self.assertEqual(test_code, modified)

    def check(self, test_code):
        self.check_with_args(test_code)
        self.check_with_args(test_code, no_leaves=True)

    def test_basic_one_liners(self):
        self.check("x = 2")
        self.check("7")
        self.check("import abc")

    def test_sequence_of_statements(self):
        self.maxDiff = None
        self.check("x = 2\ny = 3\nz = 4")
        self.assertEqual(
            python_to_s_exp("x = 2\ny = 3\nz = 4", renderer_kwargs=dict(columns=80000)),
            "(Module (/seq (Assign (list (Name &x:0 Store)) (Constant i2 None) None) (Assign (list (Name &y:0 Store)) (Constant i3 None) None) (Assign (list (Name &z:0 Store)) (Constant i4 None) None)) nil)",
        )

    def test_globals(self):
        self.assertEqual(
            python_to_s_exp("import os", renderer_kwargs=dict(columns=80)),
            "(Module (/seq (Import (list (alias g_os None)))) nil)",
        )

    def test_builtins(self):
        self.check("print(True)")
        self.check("0")
        self.check("x = None")

    def test_if_expr(self):
        self.check("2 if x == 3 else 4")

    def test_strings(self):
        self.check("' '")
        self.check("x = 'abc '")
        self.check("x = 'a=é b=\\udc80 d=\U0010ffff'")
        self.check("x = '\\uABCD'")

    def test_lambda(self):
        self.check("lambda: 1 + 2")

    def test_if(self):
        self.check("if True: pass")

    def test_unparse_sequence(self):
        # should work with or without the Module wrapper
        self.assertEqual(
            s_exp_to_python(
                "(Module (/seq (Assign (list (Name &x:0 Store)) (Constant i2 None) None)) nil)"
            ),
            "x = 2",
        )

        self.assertEqual(
            s_exp_to_python(
                "(/seq (Assign (list (Name &x:0 Store)) (Constant i2 None) None))"
            ),
            "x = 2",
        )

    @expand_with_slow_tests(len(small_set_examples()), 100)
    def test_realistic(self, i):
        try:
            print(small_set_examples()[i])
            self.check(small_set_examples()[i])
        except Exception as e:
            self.assertFalse(f"Error: {e}")
            raise e


class AbstractionCallsTest(unittest.TestCase):
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

    def test_gather_calls(self):
        calls = ParsedAST.parse_s_expression(self.ctx_in_seq).abstraction_calls()
        self.assertEqual(len(calls), 1)
        abstraction_calls = [x.to_s_exp() for x in calls.values()]
        self.assertEqual(sorted(abstraction_calls), ["(fn_1 &n:0 &s:0)"])

    def test_substitute_in_seq(self):
        seq = ParsedAST.parse_s_expression(self.ctx_in_seq)
        out = {
            x: ParsedAST.parse_python_statements("x = 2; x = 3")
            for x in seq.abstraction_calls()
        }
        substituted = seq.replace_abstraction_calls(out)

        assertSameCode(
            self,
            """
            x = 2
            x = 3
            k = s.count('8')
            """,
            substituted.to_python(),
        )

    def test_substitute_in_rooted(self):
        seq = ParsedAST.parse_s_expression(self.ctx_rooted)
        out = {
            x: ParsedAST.parse_python_statements("x = 2; x = 3")
            for x in seq.abstraction_calls()
        }
        substituted = seq.replace_abstraction_calls(out)

        assertSameCode(
            self,
            """
            if x:
                x = 2
                x = 3
            """,
            substituted.to_python(),
        )
