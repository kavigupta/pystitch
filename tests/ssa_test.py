import ast
import re
from textwrap import dedent
import unittest

import ast_scope
from python_graphs import control_flow, program_utils
from parameterized import parameterized

from imperative_stitch.analyze_program.ssa import run_ssa, rename_to_ssa
from imperative_stitch.analyze_program.ssa.banned_component import BannedComponentError
from imperative_stitch.analyze_program.ssa.render import render_phi_map
from tests.parse_test import small_set_examples


def run_ssa_on_single_function(code):
    tree, scope_info, g = get_ssa(code)
    entry_point, *_ = list(g.get_enter_blocks())
    return run_ssa_on_info(tree, scope_info, entry_point)


def run_ssa_on_multiple_functions(code):
    print(code)
    tree, scope_info, g = get_ssa(code)
    for entry_point in g.get_enter_blocks():
        print(entry_point)
        print(ast.unparse(entry_point.node))
        try:
            run_ssa_on_info(tree, scope_info, entry_point)
        except BannedComponentError:
            # don't error on this, just skip it
            pass


def get_ssa(code):
    tree = program_utils.program_to_ast(code)
    scope_info = ast_scope.annotate(tree)
    g = control_flow.get_control_flow_graph(tree)
    return tree, scope_info, g


def run_ssa_on_info(tree, scope_info, entry_point):
    _, _, phi_map, annotations = run_ssa(scope_info, entry_point)
    text = ast.unparse(rename_to_ssa(annotations, tree))
    phi_map = render_phi_map(phi_map)
    return text, phi_map


class SSATest(unittest.TestCase):
    def assert_ssa(self, code, expected):
        code, expected = dedent(code), dedent(expected)
        expected_phi_map = {
            x.group(1): x.group(2)
            for x in re.finditer(r"# ([^\s]*) = ([^\n]*)\n", expected, re.MULTILINE)
        }
        actual, phi_map = run_ssa_on_single_function(code)
        self.assertEqual(ast.unparse(ast.parse(expected)), actual)
        self.assertEqual(phi_map, expected_phi_map)

    def test_simple(self):
        code = """
        def f(x):
            x = x + 1
            return x
        """
        expected = """
        def f(x_1):
            x_2 = x_1 + 1
            return x_2
        """
        self.assert_ssa(code, expected)

    def test_if(self):
        code = """
        def f(x):
            if x > 0:
                x = x + 1
            return x
        """
        expected = """
        def f(x_1):
            if x_1 > 0:
                x_2 = x_1 + 1
            # x_3 = phi(x_1, x_2)
            return x_3
        """
        self.assert_ssa(code, expected)

    def test_if_else(self):
        code = """
        def f(x):
            if x > 0:
                x = x + 1
            else:
                x = x - 1
            return x
        """
        expected = """
        def f(x_1):
            if x_1 > 0:
                x_2 = x_1 + 1
            else:
                x_3 = x_1 - 1
            # x_4 = phi(x_2, x_3)
            return x_4
        """
        self.assert_ssa(code, expected)

    def test_while(self):
        code = """
        def f(x):
            while x > 0:
                x = x - 1
            return x
        """
        expected = """
        def f(x_1):
            # x_2 = phi(x_1, x_3)
            while x_2 > 0:
                x_3 = x_2 - 1
            return x_2
        """
        self.assert_ssa(code, expected)

    def test_uninitialized(self):
        code = """
        def f(x):
            x = x + 1
            y = x + 1
            return y
        """
        # y_2 insead of y_1 because y_1 is the uninitialized
        expected = """
        def f(x_1):
            x_2 = x_1 + 1
            y_2 = x_2 + 1
            return y_2
        """
        self.assert_ssa(code, expected)

    def test_uninitialized_branch(self):
        code = """
        def f(x):
            if x > 0:
                y = x + 1
            return x
        """
        expected = """
        def f(x_1):
            if x_1 > 0:
                y_2 = x_1 + 1
            # y_3 = phi(y_1, y_2)
            return x_1
        """
        self.assert_ssa(code, expected)

    def test_multi_branches(self):
        code = """
        def f(x):
            if x > 0:
                y = 3
            if x > 3:
                y = y + 1
            return x
        """
        expected = """
        def f(x_1):
            if x_1 > 0:
                y_2 = 3
            # y_3 = phi(y_1, y_2)
            if x_1 > 3:
                y_4 = y_3 + 1
            # y_5 = phi(y_3, y_4)
            return x_1
        """
        self.assert_ssa(code, expected)

    def test_multi_branches_then_return(self):
        code = """
        def f(x):
            if x > 0:
                y = 3
            if x > 3:
                x = y + 1
            return x
        """
        expected = """
        def f(x_1):
            if x_1 > 0:
                y_2 = 3
            # y_3 = phi(y_1, y_2)
            if x_1 > 3:
                x_2 = y_3 + 1
            # x_3 = phi(x_1, x_2)
            return x_3
        """
        self.assert_ssa(code, expected)

    def test_augadd(self):
        code = """
        def register(x):
            print(x)
            x += 1
        """
        expected = """
        def register(x_1):
            print(x_1)
            x_1_x_2 += 1
        """
        self.assert_ssa(code, expected)

    def test_inner_fn(self):
        code = """
        def f():
            def inner(check):
                pass
        """
        # 2 because _1 would be the uninitialized
        expected = """
        def f():
            def inner_2(check):
                pass
        """
        self.assert_ssa(code, expected)

    def test_for(self):
        # TODO this is wrong because of an underlying issue in python-graphs
        code = """
        def f():
            for x in range(10):
                x
            x
        """
        expected = """
        def f():
            # x_2 = phi(x_1, x_3)
            for x_3 in range(10):
                x_3
            x_3
        """
        self.assert_ssa(code, expected)

    def test_for_multi(self):
        # TODO I think this is also wrong for a similar reason
        code = """
        def f(z):
            for x, y in z:
                pass
        """
        expected = """
        def f(z_1):
            # x_2 = phi(x_1, x_3)
            # y_2 = phi(y_1, y_3)
            for x_3_x_3, y_3_y_3 in z_1:
                pass
        """
        self.assert_ssa(code, expected)

    def test_undefined_variable_referenced(self):
        code = """
        def f():
            return x
        """
        expected = """
        def f():
            return x
        """
        self.assert_ssa(code, expected)

    def test_try_except(self):
        code = """
        def f():
            try:
                x = 2
            except Exception as e:
                pass
            return e
        """
        expected = """
        def f():
            try:
                x_2 = 2
            except Exception as e_2:
                pass
            # e_3 = phi(e_1, e_2)
            return e_3
        """
        self.assert_ssa(code, expected)

