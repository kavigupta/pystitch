import ast
from textwrap import dedent
import unittest
from imperative_stitch.analyze_program.extract.errors import (
    NonInitializedInputs,
    NonInitializedOutputs,
)

from imperative_stitch.data import parse_extract_pragma
from imperative_stitch.analyze_program.extract import do_extract
from imperative_stitch.analyze_program.extract import NotApplicable


def canonicalize(code):
    code = dedent(code)
    code = ast.unparse(ast.parse(code))
    return code


class ExtractTest(unittest.TestCase):
    def run_extract(self, code):
        code = canonicalize(code)
        tree, [site] = parse_extract_pragma(code)
        # without pragmas
        code = ast.unparse(tree)
        try:
            func_def, undo = do_extract(site, tree, extract_name="__f0")
        except NotApplicable as e:
            # ensure that the code is not changed
            self.assertEqual(code, ast.unparse(tree))
            return e

        post_extract, extracted = ast.unparse(tree), ast.unparse(func_def)
        undo()
        self.assertEqual(code, ast.unparse(tree))
        return post_extract, extracted

    def assertCodes(self, expected, actual):
        post_extract, extracted = actual
        expected_post_extract, expected_extracted = expected
        self.assertEqual(
            canonicalize(expected_post_extract),
            canonicalize(post_extract),
            "post_extract",
        )
        self.assertEqual(
            canonicalize(expected_extracted), canonicalize(extracted), "extracted"
        )

    def test_basic(self):
        code = """
        def f(x, y):
            __start_extract__
            x, y = y, x
            z = x + y
            if z > 0:
                x += 1
            __end_extract__
            return x, y
        """
        post_extract_expected = """
        def f(x, y):
            x, y = __f0(x, y)
            return x, y
        """
        post_extracted = """
        def __f0(x, y):
            x, y = y, x
            z = x + y
            if z > 0:
                x += 1
            return x, y
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_basic_in_loop(self):
        code = """
        def f(xs, ys):
            zs = []
            for x, y in zip(xs, ys):
                __start_extract__
                x2y2 = x ** 2 + y ** 2
                r = x2y2 ** 0.5
                z = x + r
                __end_extract__
                zs.append(z)
            return zs
        """
        post_extract_expected = """
        def f(xs, ys):
            zs = []
            for x, y in zip(xs, ys):
                z = __f0(x, y)
                zs.append(z)
            return zs
        """
        post_extracted = """
        def __f0(x, y):
            x2y2 = x ** 2 + y ** 2
            r = x2y2 ** 0.5
            z = x + r
            return z
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_mutiple_returns(self):
        code = """
        def f(x, y):
            __start_extract__
            if x > 0:
                return x
            else:
                return y
            __end_extract__
        """
        post_extract_expected = """
        def f(x, y):
            return __f0(x, y)
        """
        post_extracted = """
        def __f0(x, y):
            if x > 0:
                return x
            else:
                return y
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def return_at_end_by_default(self):
        code = """
        def f(x, y):
            __start_extract__
            if x > 0:
                return x
            y += 1
            return y
            __end_extract__
        """
        post_extract_expected = """
        def f(x, y):
            return __f0(x, y)
        """
        post_extracted = """
        def __f0(x, y):
            if x > 0:
                return x
            y += 1
            return y
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_augadd(self):
        code = """
        def f(x, y):
            __start_extract__
            x += y
            __end_extract__
            return x
        """
        post_extract_expected = """
        def f(x, y):
            x = __f0(x, y)
            return x
        """
        post_extracted = """
        def __f0(x, y):
            x += y
            return x
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_do_not_add_return(self):
        code = """
        def f(x, y):
            __start_extract__
            x = y
            __end_extract__
        """
        post_extract_expected = """
        def f(x, y):
            return __f0(y)
        """
        post_extracted = """
        def __f0(y):
            x = y
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_undefined_input(self):
        code = """
        def f(x):
            if x > 0:
                y = 2
            __start_extract__
            if x > 3:
                x += y
            __end_extract__
            return x
        """
        self.assertEqual(self.run_extract(code), NonInitializedInputs())

    def test_undefined_output(self):
        code = """
        def f(x):
            __start_extract__
            if x > 3:
                y = 7
            __end_extract__
            if x > 5:
                x += y
            return x
        """
        self.assertEqual(self.run_extract(code), NonInitializedOutputs())
