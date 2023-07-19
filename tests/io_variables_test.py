import ast_scope
import unittest
from imperative_stitch.analyze_program.extract.errors import (
    ClosureOverVariableModifiedInExtractedCode,
    ModifiesVariableClosedOverInNonExtractedCode,
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
        site.inject_sentinel()
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
            Variables(
                [],
                [],
                [("x", 3)],
                errors=[ModifiesVariableClosedOverInNonExtractedCode],
            ),
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

    def test_nontrivial_control_flow(self):
        code = """
        def f():
            if True:
                x = 1
            else:
                x = 2
            __start_extract__
            while False:
                print
            __end_extract__
            lambda: x
            x = 3
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([], [], []),
        )

    def test_nontrivial_control_flow_2(self):
        code = """
        def f():
            __start_extract__
            x = 0
            y = 0
            while True:
                x = 3
            __end_extract__
            while True:
                if True:
                    y = 2
                    break
                if True:
                    y = 3
            print(x)
            print(y)
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([], [], [("x", 3), ("y", 6)]),
        )

    def test_nontrivial_control_flow_3(self):
        code = """
        def _main():
            if True:
                __start_extract__
                x = 1
                __end_extract__
            else:
                x = 2
                while True:
                    x = 3
            print(x)
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([], [], [("x", 6)]),
        )

    def test_nontrivial_control_flow_4(self):
        code = """
        def f():
            n = 2
            try:
                n = n - 1
            except:
                __start_extract__
                pass
                __end_extract__
            return n
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([], [], []),
        )

    def test_re_reference_in_group(self):
        code = """
        def _main():
            i = 2
            while True:
                __start_extract__
                i = i + 1
                __end_extract__
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([("i", 3)], [], [("i", 3)]),
        )

    def test_re_reference_in_group_with_metavariable(self):
        code = """
        def _main():
            i = 2
            while True:
                __start_extract__
                i = {__metavariable__, __m1, i} + 1
                __end_extract__
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([("i", 3)], [], [("i", 3)]),
        )

    def test_assign_to_closed(self):
        code = """
        def f():
            def g():
                return A
            __start_extract__
            A = 2
            g()
            __end_extract__
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables(
                [("g", 2)],
                [],
                [],
                errors=[ModifiesVariableClosedOverInNonExtractedCode],
            ),
        )

    def test_variable_closed_over_by_later_variable(self):
        code = """
        def f():
            __start_extract__
            u = lambda: {__metavariable__, __m0, n}
            __end_extract__
            n = 3
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([], [("n", 3)], []),
        )

    def test_variable_closed_over_by_later_variable_2(self):
        code = """
        def f():
            before
            __start_extract__
            inside
            u = lambda: __m0(n)
            __end_extract__
            n = 3
        """
        self.assertSameVariables(
            self.run_io(code),
            Variables([], [("n", 3)], []),
        )
