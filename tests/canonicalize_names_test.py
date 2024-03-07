import ast
import unittest

from imperative_stitch.parser.symbol import canonicalize_names

from .utils import canonicalize


class CanonicalizeNamesTest(unittest.TestCase):
    def assertCanonicalized(self, code, expected):
        code, expected = canonicalize(code), canonicalize(expected)
        actual = ast.unparse(canonicalize_names(ast.parse(code)))
        self.assertEqual(expected, actual)

    def test_simple(self):
        self.assertCanonicalized(
            """
            def f(x):
                return x
            """,
            """
            def _0(_1):
                return _1   
            """,
        )

    def test_multiple_uses(self):
        self.assertCanonicalized(
            """
            x = 3
            y = x
            z = x + y
            """,
            """
            _0 = 3
            _1 = _0
            _2 = _0 + _1
            """,
        )
