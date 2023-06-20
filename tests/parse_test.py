import ast
from functools import lru_cache
import json
import os

import unittest
from parameterized import parameterized
import tqdm.auto as tqdm
from s_expression_parser import parse, ParserConfig, Pair

from imperative_stitch.to_s import pair_to_s_exp, python_to_s_exp, s_exp_to_python
from imperative_stitch.utils.recursion import recursionlimit


@lru_cache(None)
def small_set_examples():
    with open("data/small_set.json") as f:
        contents = json.load(f)
    return contents


class ParseUnparseInverseTest(unittest.TestCase):
    def canonicalize(self, python_code):
        return ast.unparse(ast.parse(python_code))

    def assert_valid_s_exp(self, s_exp):
        if not isinstance(s_exp, list):
            return
        self.assertTrue(
            isinstance(s_exp[0], type) or s_exp[0] in {"semi", "empty"}, repr(s_exp[0])
        )
        # self.assertTrue(len(s_exp) > 1, repr(s_exp))
        for y in s_exp[1:]:
            self.assert_valid_s_exp(y)

    def check(self, test_code):
        test_code = self.canonicalize(test_code)
        s_exp = python_to_s_exp(test_code, renderer_kwargs=dict(columns=80))
        # print(s_exp)
        with recursionlimit(max(1500, len(s_exp))):
            [s_exp_parsed] = parse(
                s_exp, ParserConfig(prefix_symbols=[], dots_are_cons=False)
            )
            s_exp_parsed = pair_to_s_exp(s_exp_parsed)
        print(repr(s_exp_parsed))
        self.assert_valid_s_exp(s_exp_parsed)
        modified = s_exp_to_python(s_exp)
        self.assertEqual(test_code, modified)

    def test_basic_one_liners(self):
        self.check("x = 2")
        self.check("7")
        self.check("import abc")

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

    @parameterized.expand([(i,) for i in range(len(small_set_examples()))])
    def test_realistic(self, i):
        try:
            self.check(small_set_examples()[i])
        except Exception as e:
            self.assertFalse(f"Error: {e}")
