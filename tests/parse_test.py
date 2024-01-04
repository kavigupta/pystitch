import ast
import unittest

from s_expression_parser import ParserConfig, parse

from imperative_stitch.parser import python_to_s_exp, s_exp_to_python, ParsedAST
from imperative_stitch.utils.recursion import recursionlimit

from .utils import expand_with_slow_tests, small_set_examples


class ParseUnparseInverseTest(unittest.TestCase):
    def canonicalize(self, python_code):
        return ast.unparse(ast.parse(python_code))

    def assert_valid_s_exp(self, s_exp):
        if not isinstance(s_exp, list) or not s_exp:
            return
        if s_exp[0] not in {"/seq"}:
            self.assertTrue(isinstance(s_exp[0], type), repr(s_exp[0]))
            self.assertTrue(len(s_exp) > 1, repr(s_exp))
        for y in s_exp[1:]:
            self.assert_valid_s_exp(y)

    def check(self, test_code):
        test_code = self.canonicalize(test_code)
        s_exp = python_to_s_exp(test_code, renderer_kwargs=dict(columns=80))
        # print(s_exp)
        s_exp_parsed = ParsedAST.parse_s_expression(s_exp)
        print(repr(s_exp_parsed))
        self.assert_valid_s_exp(s_exp_parsed)
        modified = s_exp_to_python(s_exp)
        self.assertEqual(test_code, modified)

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

    @expand_with_slow_tests(len(small_set_examples()))
    def test_realistic(self, i):
        try:
            print(small_set_examples()[i])
            self.check(small_set_examples()[i])
        except Exception as e:
            self.assertFalse(f"Error: {e}")
            raise e
