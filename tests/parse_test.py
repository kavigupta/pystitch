import ast
import os

import unittest
import tqdm.auto as tqdm

from imperative_stitch.to_s import python_to_s_exp, s_exp_to_python


class ParseUnparseInverseTest(unittest.TestCase):
    def canonicalize(self, python_code):
        return ast.unparse(ast.parse(python_code))

    def check(self, test_code):
        test_code = self.canonicalize(test_code)
        modified = s_exp_to_python(
            python_to_s_exp(test_code, renderer_kwargs=dict(columns=80))
        )
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

    def test_lambda(self):
        self.check("lambda: 1 + 2")

    def realistic_test(self):
        # TODO this is device-dependent
        # this should be replaced
        paths = [
            os.path.join(root, file)
            for root, _, files in os.walk("/home/kavi/mit/ExpeditionsBioDev/")
            for file in files
            if file.endswith(".py")
        ]
        contents = [(k, open(k).read()) for k in paths]
        contents = sorted(contents, key=lambda x: len(x[1]))
        for path, content in tqdm.tqdm(contents):
            print(path)
            try:
                self.canonicalize(path)
            except SyntaxError:
                continue
            try:
                self.check(content)
            except Exception as e:
                self.assertFalse(f"Error: {e}")
