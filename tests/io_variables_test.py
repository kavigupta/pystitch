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

    def assertSameVariables(self, actual, expected):
        self.maxDiff = None
        self.assertEqual(str(actual), str(expected))

    def test_basic(self):
        code = """
        def f(y):
            __start_extract__
            x = 3
            x = x + y
            __end_extract__
            return x
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([("y", 1)], [], [("x", 3)]),
        )

    def test_same_io(self):
        code = """
        def f(x, y):
            __start_extract__
            y = x = x + y
            __end_extract__
            return x, y
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([("x", 1), ("y", 1)], [], [("x", 2), ("y", 2)]),
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
        self.assertSameVariables(
            self.run_io(code),
            Variables([("y", 1)], [("x", 3)], [("z", 2)]),
        )

    def test_closed_if_not_entirely_within_section_def(self):
        self.maxDiff = None
        code = """
        def f(x, y):
            __start_extract__
            def z():
                return x + y
            __end_extract__
            x = 2
            return z
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([("y", 1)], [("x", 3)], [("z", 2)]),
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
        self.assertSameVariables(
            self.run_io(code),
            Variables([("y", 1)], [], [("z", 2)]),
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
        self.assertSameVariables(
            self.run_io(code),
            Variables(
                [("y", 1)],
                [("x", 4)],
                [("z", 2)],
                errors=[ClosureOverVariableModifiedInExtractedCode],
            ),
        )

    def test_conditionally_initializing_a_variable_you_must_return(self):
        code = """
        def _main(i):
            count = 2
            __start_extract__
            if i == '8':
                count = 7
            __end_extract__
            return count
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([("count", 2), ("i", 1)], [], [("count", 4)]),
        )

    def test_capturing_non_global_from_parent(self):
        code = """
        def f():
            func = 2
            def g():
                __start_extract__
                func
                __end_extract__
            return g
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([], [], [], ["func"]),
        )

    def test_dont_capture_non_global_from_child(self):
        code = """
        def f():
            __start_extract__
            lambda func: func
            __end_extract__
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([], [], []),
        )

    def test_inside_loop(self):
        code = """
        def f():
            while left <= right:
                __start_extract__
                mid = (left + right) // 2
                __end_extract__
            mid
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([], [], [("mid", 2)]),
        )

    def test_inside_loop_immediate(self):
        # see ssa_test.py::SSATest::test_inside_loop_immediate
        code = """
        def f():
            while left <= right:
                __start_extract__
                mid = (left + right) // 2
                __end_extract__
                mid
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([], [], [("mid", 3)]),
        )

    def test_site_defines_variable_referenced_in_closure_above(self):
        code = """
        def f():
            def g():
                return x
            __start_extract__
            x = 2
            __end_extract__
            return g
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([], [], [("x", 3)]),
        )

    def test_variable_only_referenced_in_loop(self):
        code = """
        def f():
            x = 0
            y = 0
            while y < 10:
                __start_extract__
                x = x + 1
                y = x
                z = 2
                z = z + 1
                __end_extract__
            return y
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([("x", 3)], [], [("x", 3), ("y", 3)]),
        )

    def test_return_both(self):
        code = """
        def f(x, y):
            __start_extract__
            y = y + 1
            x = lambda: y
            __end_extract__
            return x, y
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([("y", 1)], [], [("x", 2), ("y", 2)]),
        )
