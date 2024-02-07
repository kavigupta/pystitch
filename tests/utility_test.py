import unittest
from textwrap import dedent

from imperative_stitch.utils.wrap import unwrap, wrap
from tests.utils import canonicalize


class WrapTest(unittest.TestCase):
    def assertSameCode(self, expected, actual):
        self.assertEqual(canonicalize(expected), canonicalize(actual))

    def test_basic_wrap(self):
        code = "x = 3"
        expected = dedent(
            """
            def _main():
                x = 3
            _main()
            """
        )
        self.assertSameCode(wrap(code), expected)

    def test_wrap_with_imports(self):
        code = dedent(
            """
            import os
            from math import sqrt
            x = 3
            """
        )
        expected = dedent(
            """
            import os
            from math import sqrt
            def _main():
                x = 3
            _main()
            """
        )
        self.assertSameCode(wrap(code), expected)

    def test_unwrap_basic(self):
        code = dedent(
            """
            def _main():
                x = 3
            _main()
            """
        )
        expected = "x = 3"
        self.assertSameCode(unwrap(code), expected)

    def test_unwrap_with_imports(self):
        code = dedent(
            """
            import os
            from math import sqrt
            def _main():
                x = 3
            _main()
            """
        )
        expected = dedent(
            """
            import os
            from math import sqrt
            x = 3
            """
        )
        self.assertSameCode(unwrap(code), expected)

    def test_unwrap_empty(self):
        code = dedent(
            """
            def _main():
                pass
            _main()
            """
        )
        expected = ""
        self.assertSameCode(unwrap(code), expected)

    def test_unwrap_with_return(self):
        code = dedent(
            """
            def _main():
                return 3
            _main()
            """
        )
        expected = "3"
        self.assertSameCode(unwrap(code), expected)

    def test_unwrap_with_internal_return(self):
        code = dedent(
            """
            def _main():
                x = 3
                def _inner():
                    return x
                if x == 2:
                    return x
            _main()
            """
        )
        expected = dedent(
            """
            x = 3
            def _inner():
                return x
            if x == 2:
                x
            """
        )
        self.assertSameCode(unwrap(code), expected)
