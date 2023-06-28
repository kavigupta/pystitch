import ast
import re
from textwrap import dedent
import unittest

import ast_scope
from python_graphs import control_flow, program_utils
from parameterized import parameterized
import timeout_decorator

from imperative_stitch.analyze_program.ssa import run_ssa, rename_to_ssa
from imperative_stitch.analyze_program.ssa.banned_component import BannedComponentError
from imperative_stitch.analyze_program.ssa.render import render_phi_map
from imperative_stitch.analyze_program.structures.per_function_cfg import PerFunctionCFG
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


@timeout_decorator.timeout(10)
def run_ssa_on_info(tree, scope_info, entry_point):
    _, _, phi_map, annotations = run_ssa(scope_info, PerFunctionCFG(entry_point))
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
        self.assertEqual(expected_phi_map, phi_map)

    def test_empty(self):
        code = """
        def f(x):
            pass
        """
        expected = """
        def f(x_1):
            pass
        """
        self.assert_ssa(code, expected)

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

    def test_if_followed_by_if(self):
        code = """
        def f(x):
            if x > 0:
                x = x + 1
            if x > 1:
                x = x + 1
            return x
        """
        expected = """
        def f(x_1):
            if x_1 > 0:
                x_2 = x_1 + 1
            # x_3 = phi(x_1, x_2)
            if x_3 > 1:
                x_4 = x_3 + 1
            # x_5 = phi(x_3, x_4)
            return x_5
        """
        self.assert_ssa(code, expected)

    def test_if_followed_by_while(self):
        code = """
        def f(x):
            if x > 0:
                x = x + 1
            while x > 1:
                x = x + 1
            return x
        """
        expected = """
        def f(x_1):
            if x_1 > 0:
                x_2 = x_1 + 1
            # x_3 = phi(x_1, x_2, x_4)
            while x_3 > 1:
                x_4 = x_3 + 1
            return x_3
        """
        self.assert_ssa(code, expected)

    def test_complex_control_flow(self):
        code = """
        def main():
            if True:
                f = 2
                u = f
            print
            while True:
                if 2:
                    2
                x = 2
        """
        expected = """
        def main():
            if True:
                f_2 = 2
                u_2 = f_2
            # f_3 = phi(f_1, f_2)
            # u_3 = phi(u_1, u_2)
            print
            # x_2 = phi(x_1, x_3)
            # f_4 = phi(f_3, f_4)
            # u_4 = phi(u_3, u_4)
            while True:
                if 2:
                    2
                x_3 = 2
        """
        self.assert_ssa(code, expected)

    def test_continue(self):
        code = """
        def f(x):
            while True:
                x = x + 1
                continue
                x = x + 2
            return x
        """
        expected = """
        def f(x_1):
            # x_2 = phi(x_1, x_3)
            while True:
                x_3 = x_2 + 1
                continue
                x = x + 2
            return x_2
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

    def test_while_then_end(self):
        code = """
        def f():
            while True:
                x = 2
        """
        expected = """
        def f():
            # x_2 = phi(x_1, x_3)
            while True:
                x_3 = 2
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
            x_2
        """
        self.assert_ssa(code, expected)

    def test_for_else_without_break(self):
        code = """
        def f():
            for x in range(10):
                x
            else:
                x = 4
            return x
        """
        expected = """
        def f():
            # x_2 = phi(x_1, x_3)
            for x_3 in range(10):
                x_3
            else:
                x_4 = 4
            return x_4
        """
        self.assert_ssa(code, expected)

    def test_for_else_with_break(self):
        code = """
        def f():
            for x in range(10):
                x
                if x > 5:
                    x = 7
                    break
            else:
                x = 4
            return x
        """
        expected = """
        def f():
            # x_2 = phi(x_1, x_3)
            for x_3 in range(10):
                x_3
                if x_3 > 5:
                    x_4 = 7
                    break
            else:
                x_5 = 4
            # x_6 = phi(x_4, x_5)
            return x_6
        """
        self.assert_ssa(code, expected)

    def test_for_multi(self):
        code = """
        def f(z):
            for x, y in z:
                pass
        """
        expected = """
        def f(z_1):
            # x_2 = phi(x_1, x_3)
            # y_2 = phi(y_1, y_3)
            for x_3, y_3 in z_1:
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
                x, y
                y = 3
                x, y
            except Exception as e:
                x, y
                pass
            return e, x, y
        """
        expected = """
        def f():
            try:
                x_2 = 2
                x_2, y_1
                y_2 = 3
                x_2, y_2
            except Exception as e_2:
                # x_3 = phi(x_1, x_2)
                # y_3 = phi(y_1, y_2)
                x_3, y_3
                pass
            # e_3 = phi(e_1, e_2)
            # x_4 = phi(x_2, x_3)
            # y_4 = phi(y_2, y_3)
            return e_3, x_4, y_4
        """
        self.assert_ssa(code, expected)

    def test_arguments_simple(self):
        code = """
        def f(x, y, z, *abc,  a=2, b=3, **kwargs):
            return x
        """
        expected = """
        def f(x_1, y_1, z_1, *abc_1, a_1=2, b_1=3, **kwargs_1):
            return x_1
        """
        self.assert_ssa(code, expected)

    def test_arguments_positional(self):
        code = """
        def f(x, y, /, z):
            return x
        """
        expected = """
        def f(x_1, y_1, /, z_1):
            return x_1
        """
        self.assert_ssa(code, expected)

    def test_arguments_simple_types(self):
        code = """
        def f(x: int, y: str):
            return x
        """
        expected = """
        def f(x_1: int, y_1: str):
            
            return x_1
        """
        self.assert_ssa(code, expected)

    def test_arguments_complex_type_single(self):
        code = """
        def f(x: List[int]):
            return x
        """
        expected = """
        def f(x_1: List[int]):
            return x_1
        """
        self.assert_ssa(code, expected)

    def test_arguments_complex_types(self):
        code = """
        def f(x: List[int], y: Dict[str, int], z: Set[int], *abc: List[int],  a: List[int]=2, b: List[int]=3, **kwargs: List[int]):
            return x
        """
        expected = """
        def f(x_1: List[int], y_1: Dict[str, int], z_1: Set[int], *abc_1: List[int], a_1: List[int]=2, b_1: List[int]=3, **kwargs_1: List[int]):
            
            return x_1
        """
        self.assert_ssa(code, expected)

    def test_with_sub_function(self):
        # TODO handle contained variables
        code = """
        def f():
            x = 2
            def g():
                return x
            def h(x):
                return x
            return g
        """
        expected = """
        def f():
            x_2 = 2
            def g_2():
                return x
            def h_2(x):
                return x
            return g_2
        """
        self.assert_ssa(code, expected)

    def test_with_sub_lambda(self):
        code = """
        def f():
            x = 2
            g = lambda: x
            h = lambda x: x
            return g
        """
        expected = """
        def f():
            x_2 = 2
            # x_3 = gamma(x_2)
            g_2 = lambda: x_3
            h_2 = lambda x: x
            return g_2
        """
        self.assert_ssa(code, expected)

    def test_with_sub_lambda_several(self):
        code = """
        def f():
            x = 1
            x = 2
            g = lambda: x
            x = 3
            return g
        """
        expected = """
        def f():
            x_2 = 1
            x_3 = 2
            # x_5 = gamma(x_3; x_4)
            g_2 = lambda: x_5
            x_4 = 3
            return g_2
        """
        self.assert_ssa(code, expected)

    def test_with_sub_lambda_same_line(self):
        code = """
        def f():
            x = 1
            x = lambda: x
            return x_3
        """
        expected = """
        def f():
            x_2 = 1
            # x_4 = gamma(x_2; x_3)
            x_3 = lambda: x_4
            return x_3
        """
        self.assert_ssa(code, expected)

    def test_with_comprehensions(self):
        code = """
        def f():
            x = 2
            [x for _ in range(2)]
            {x for _ in range(2)}
            {x : 1 for _ in range(2)}
            (x for _ in range(2))

            [x for x in range(2)]
            {x for x in range(2)}
            {x : 1 for x in range(2)}
            (x for x in range(2))
            return x
        """
        expected = """
        def f():
            x_2 = 2
            [x_2 for _ in range(2)]
            {x_2 for _ in range(2)}
            {x_2 : 1 for _ in range(2)}
            # x_3 = gamma(x_2)
            (x_3 for _ in range(2))

            [x for x in range(2)]
            {x for x in range(2)}
            {x : 1 for x in range(2)}
            (x for x in range(2))

            return x_2
        """
        self.assert_ssa(code, expected)


class SSARealisticTest(unittest.TestCase):
    @parameterized.expand([(i,) for i in range(len(small_set_examples()))])
    def test_realistic(self, i):
        run_ssa_on_multiple_functions(small_set_examples()[i])
