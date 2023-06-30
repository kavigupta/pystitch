import ast_scope
import unittest
from imperative_stitch.analyze_program.extract.errors import (
    ClosureOverVariableModifiedInExtractedCode,
)
from imperative_stitch.analyze_program.extract.input_output_variables import (
    Variables,
    compute_variables,
)

from imperative_stitch.data.parse_extract import parse_extract_pragma

from .utils import canonicalize


class ReplaceBreakAndContinueTest(unittest.TestCase):
    def run_io(self, code):
        code = canonicalize(code)
        tree, [site] = parse_extract_pragma(code)
        scope_info = ast_scope.annotate(tree)
        pfcfg = site.locate_entry_point(tree)
        return compute_variables(site, scope_info, pfcfg)

    def test_basic(self):
        code = """
        def f(y):
            __start_extract__
            x = 3
            x = x + y
            __end_extract__
            return x
        """
        self.assertEqual(
            self.run_io(code),
            Variables(input_vars=["y"], closed_vars=[], output_vars=["x"]),
        )

    def test_same_io(self):
        code = """
        def f(x, y):
            __start_extract__
            y = x = x + y
            __end_extract__
            return x, y
        """
        self.assertEqual(
            self.run_io(code),
            Variables(input_vars=["x", "y"], closed_vars=[], output_vars=["x", "y"]),
        )

    def test_closed_if_not_entirely_within_section(self):
        self.maxDiff = None
        code = """
        def f(x, y):
            __start_extract__
            z = lambda: x + y
            __end_extract__
            x = 2
            return z
        """
        self.assertEqual(
            str(self.run_io(code)),
            str(Variables(input_vars=["y"], closed_vars=["x"], output_vars=["z"])),
        )

    def test_not_closed_if_entirely_within_section(self):
        code = """
        def f(x, y):
            __start_extract__
            x = 3
            z = lambda: x + y
            x = 2
            __end_extract__
            return z
        """
        self.assertEqual(
            self.run_io(code),
            Variables(input_vars=["y"], closed_vars=[], output_vars=["z"]),
        )

    def test_error_if_not_entirely_closed(self):
        self.maxDiff = None
        code = """
        def f(x, y):
            __start_extract__
            z = lambda: x + y
            x = 2
            __end_extract__
            x = 5
            return z
        """
        self.assertEqual(
            str(self.run_io(code)),
            str(
                Variables(
                    input_vars=["y"],
                    closed_vars=["x"],
                    output_vars=["z"],
                    errors=[ClosureOverVariableModifiedInExtractedCode],
                )
            ),
        )
