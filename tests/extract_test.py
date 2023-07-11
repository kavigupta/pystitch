import ast
import copy
import unittest
import numpy as np
from parameterized import parameterized

from imperative_stitch.analyze_program.extract.errors import (
    ClosedVariablePassedDirectly,
    ClosureOverVariableModifiedInExtractedCode,
    MultipleExits,
    NonInitializedInputs,
    NonInitializedOutputs,
)
from imperative_stitch.analyze_program.ssa.banned_component import BannedComponentError

from imperative_stitch.data import parse_extract_pragma
from imperative_stitch.analyze_program.extract import do_extract
from imperative_stitch.analyze_program.extract import NotApplicable
from imperative_stitch.utils.ast_utils import (
    ReplaceNodes,
    ast_nodes_in_order,
    field_is_body,
)
from imperative_stitch.utils.classify_nodes import compute_types_each
from tests.parse_test import small_set_examples
from python_graphs import control_flow

from tests.utils import canonicalize


class GenericExtractTest(unittest.TestCase):
    def run_extract(self, code, num_metavariables=None):
        code = canonicalize(code)
        tree, [site] = parse_extract_pragma(code)
        if num_metavariables is not None:
            self.assertEqual(len(site.metavariables), num_metavariables)
        return self.run_extract_from_tree(tree, site)

    def run_extract_from_tree(self, tree, site):
        # without pragmas
        code = ast.unparse(tree)
        try:
            extr = do_extract(site, tree, extract_name="__f0")
        except (NotApplicable, BannedComponentError) as e:
            # ensure that the code is not changed
            self.assertEqual(code, ast.unparse(tree))
            return e

        post_extract, extracted = ast.unparse(tree), ast.unparse(extr.func_def)
        extr.undo()
        self.assertEqual(code, ast.unparse(tree), "undo")
        return post_extract, extracted

    def assertCodes(self, expected, actual):
        self.maxDiff = None
        post_extract, extracted = actual
        expected_post_extract, expected_extracted = expected

        post_extract, extracted = canonicalize(post_extract), canonicalize(extracted)
        expected_post_extract, expected_extracted = (
            canonicalize(expected_post_extract),
            canonicalize(expected_extracted),
        )

        expected = expected_post_extract + "\n" + "=" * 80 + "\n" + expected_extracted
        actual = post_extract + "\n" + "=" * 80 + "\n" + extracted

        self.assertEqual(expected, actual)


class ExtractTest(GenericExtractTest):
    def test_pass(self):
        code = """
        def f(x):
            __start_extract__
            pass
            __end_extract__
        """
        post_extract_expected = """
        def f(x):
            __f0()
        """
        post_extracted = """
        def __f0():
            pass
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
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
        def __f0(__0, __1):
            __0, __1 = __1, __0
            __2 = __0 + __1
            if __2 > 0:
                __0 += 1
            return __0, __1
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_no_return(self):
        code = """
        def f(x, y):
            __start_extract__
            print(x, y)
            print(x ** 2)
            __end_extract__
            z = x + y
            if z > 0:
                x += 1
            return x, y
        """
        post_extract_expected = """
        def f(x, y):
            __f0(x, y)
            z = x + y
            if z > 0:
                x += 1
            return x, y
        """
        post_extracted = """
        def __f0(__0, __1):
            print(__0, __1)
            print(__0 ** 2)
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
        def __f0(__1, __2):
            __0 = __1 ** 2 + __2 ** 2
            __3 = __0 ** 0.5
            __4 = __1 + __3
            return __4
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_only_affects_loop(self):
        code = """
        def f(x):
            while True:
                __start_extract__
                x = x + 1
                __end_extract__
            return x
        """
        post_extract_expected = """
        def f(x):
            while True:
                x = __f0(x)
            return x
        """
        post_extracted = """
        def __f0(__0):
            __0 = __0 + 1
            return __0
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
        def __f0(__0, __1):
            if __0 > 0:
                return __0
            else:
                return __1
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
        def __f0(__0, __1):
            if __0 > 0:
                return __0
            __1 += 1
            return __1
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
        def __f0(__0, __1):
            __0 += __1
            return __0
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
        def __f0(__1):
            __0 = __1
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_inside_if(self):
        code = """
        def f(x, y):
            if x > 0:
                __start_extract__
                x += y
                __end_extract__
            return x
        """
        post_extract_expected = """
        def f(x, y):
            if x > 0:
                x = __f0(x, y)
            return x
        """
        post_extracted = """
        def __f0(__0, __1):
            __0 += __1
            return __0
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_inside_else(self):
        code = """
        def f(x, y):
            if x > 0:
                x += y
            else:
                __start_extract__
                x += y
                __end_extract__
            return x
        """
        post_extract_expected = """
        def f(x, y):
            if x > 0:
                x += y
            else:
                x = __f0(x, y)
            return x
        """
        post_extracted = """
        def __f0(__0, __1):
            __0 += __1
            return __0
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_conditional_early_return(self):
        code = """
        def f(x, y):
            __start_extract__
            if x > 0:
                return x
            x += 1
            __end_extract__
            x += y
            return x
        """
        self.assertEqual(self.run_extract(code), MultipleExits())

    def test_conditional_break(self):
        code = """
        def f(x, y):
            for _ in range(10):
                __start_extract__
                if x > 0:
                    break
                x += 1
                __end_extract__
            x += y
            return x
        """
        self.assertEqual(self.run_extract(code), MultipleExits())

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

    def test_nonlocal(self):
        code = """
        def f(x):
            def g():
                nonlocal x
                x = x + 1
                return x
            __start_extract__
            y = g()
            __end_extract__
            return y
        """
        self.assertEqual(
            self.run_extract(code),
            BannedComponentError(
                "nonlocal statements cannot be used because we do not support them yet"
            ),
        )

    def test_within_try(self):
        code = """
        def f(x):
            try:
                __start_extract__
                x = h(x)
                x = g(x)
                __end_extract__
            except:
                pass
            return x
        """
        post_extract_expected = """
        def f(x):
            try:
                x = __f0(x)
            except:
                pass
            return x
        """
        post_extracted = """
        def __f0(__0):
            __0 = h(__0)
            __0 = g(__0)
            return __0
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_within_try_with_raise(self):
        code = """
        def f(x):
            try:
                __start_extract__
                raise RuntimeError
                __end_extract__
            except:
                y = 2
            return x
        """
        post_extract_expected = """
        def f(x):
            try:
                __f0()
            except:
                y = 2
            return x
        """
        post_extracted = """
        def __f0():
            raise RuntimeError
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_always_breaks(self):
        code = """
        def f(x):
            while True:
                __start_extract__
                x = x + 1
                break
                __end_extract__
                x = x + 2
            return x
        """
        post_extract_expected = """
        def f(x):
            while True:
                x = __f0(x)
                break
                x = x + 2
            return x
        """
        post_extracted = """
        def __f0(__0):
            __0 = __0 + 1
            return __0
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_always_continues(self):
        code = """
        def f(x):
            while True:
                __start_extract__
                x = x + 1
                continue
                __end_extract__
                x = x + 2
            return x
        """
        post_extract_expected = """
        def f(x):
            while True:
                x = __f0(x)
                continue
                x = x + 2
            return x
        """
        post_extracted = """
        def __f0(__0):
            __0 = __0 + 1
            return __0
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_always_breaks_in_if(self):
        code = """
        def f(x):
            while True:
                __start_extract__
                if x > 0:
                    break
                else:
                    x = x + 1
                    break
                __end_extract__
                x = x + 2
            return x
        """
        post_extract_expected = """
        def f(x):
            while True:
                x = __f0(x)
                break
                x = x + 2
            return x
        """
        post_extracted = """
        def __f0(__0):
            if __0 > 0:
                return __0
            else:
                __0 = __0 + 1
                return __0
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_always_continues_in_if(self):
        code = """
        def f(x):
            while True:
                __start_extract__
                if x > 0:
                    continue
                else:
                    x = x + 1
                    continue
                __end_extract__
                x = x + 2
            return x
        """
        post_extract_expected = """
        def f(x):
            while True:
                x = __f0(x)
                continue
                x = x + 2
            return x
        """
        post_extracted = """
        def __f0(__0):
            if __0 > 0:
                return __0
            else:
                __0 = __0 + 1
                return __0
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_normal_control_flow_if_autocontinue_anyway(self):
        code = """
        def f(x):
            while True:
                __start_extract__
                if x > 0:
                    continue
                else:
                    x = x + 1
                    continue
                __end_extract__
            return x
        """
        post_extract_expected = """
        def f(x):
            while True:
                x = __f0(x)
            return x
        """
        post_extracted = """
        def __f0(__0):
            if __0 > 0:
                return __0
            else:
                __0 = __0 + 1
                return __0
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_extract_y_then_x(self):
        code = """
        def f(x, y):
            __start_extract__
            y = y + 1
            x = x + 1
            __end_extract__
            return x, y
        """
        post_extract_expected = """
        def f(x, y):
            y, x = __f0(y, x)
            return x, y
        """
        post_extracted = """
        def __f0(__0, __1):
            __0 = __0 + 1
            __1 = __1 + 1
            return __0, __1
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_extract_lambda_not_redefined(self):
        code = """
        def f(x, y):
            __start_extract__
            x = lambda: y
            __end_extract__
            return x, y
        """
        post_extract_expected = """
        def f(x, y):
            x = __f0(y)
            return x, y
        """
        post_extracted = """
        def __f0(__1):
            __0 = lambda: __1
            return __0
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_extract_lambda_redefined_internally(self):
        code = """
        def f(x, y):
            __start_extract__
            x = lambda: y
            y = 2
            __end_extract__
            return x
        """
        self.assertEqual(
            self.run_extract(code), ClosureOverVariableModifiedInExtractedCode()
        )

    def test_extract_lambda_redefined_externally(self):
        code = """
        def f(x, y):
            __start_extract__
            x = lambda: y
            __end_extract__
            y = 2
            return x
        """
        self.assertEqual(self.run_extract(code), ClosedVariablePassedDirectly())

    def test_extract_with_lambda(self):
        code = """
        def f(x, y):
            __start_extract__
            y = y + 1
            x = lambda: y
            __end_extract__
            return x, y
        """
        post_extract_expected = """
        def f(x, y):
            y, x = __f0(y)
            return x, y
        """
        post_extracted = """
        def __f0(__0):
            __0 = __0 + 1
            __1 = lambda: __0
            return __0, __1
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_not_in_scope_canonicalized_separately(self):
        code = """
        def f(y):
            __start_extract__
            x = sum(y)
            lambda z: z
            lambda y: y
            __end_extract__
        """
        post_extract_expected = """
        def f(y):
            return __f0(y)
        """
        post_extracted = """
        def __f0(__1):
            __0 = sum(__1)
            lambda __2: __2
            lambda __3: __3
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_extract_with_lambda_reassign(self):
        code = """
        def f(x, y):
            __start_extract__
            y = y + 1
            x = lambda: y
            __end_extract__
            y = 2
            return x, y
        """
        self.assertEqual(
            self.run_extract(code), ClosureOverVariableModifiedInExtractedCode()
        )

    def test_extract_with_called_lambda(self):
        code = """
        def f(x, y):
            __start_extract__
            x = x ** 3
            z = lambda k: y ** (x - y) * (lambda x: x)(y) + k
            __end_extract__
        """
        post_extract_expected = """
        def f(x, y):
            return __f0(x, y)
        """
        post_extracted = """
        def __f0(__0, __2):
            __0 = __0 ** 3
            __1 = lambda __3: __2 ** (__0 - __2) * (lambda __4: __4)(__2) + __3
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )


class RewriteTest(GenericExtractTest):
    def test_basic_rewrite(self):
        code = """
        def f(x, y):
            __start_extract__
            z = x ** 2 + {__metavariable__, __m1, y ** 2}
            __end_extract__
            return z
        """
        post_extract_expected = """
        def f(x, y):
            z = __f0(x, lambda: y ** 2)
            return z
        """
        post_extracted = """
        def __f0(__1, __m1):
            __0 = __1 ** 2 + __m1()
            return __0
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_rewrite_capturing_a_variable(self):
        code = """
        def f(x):
            __start_extract__
            y = x ** 7
            z = {__metavariable__, __m1, y ** 7 - y}
            __end_extract__
            return z
        """
        post_extract_expected = """
        def f(x):
            z = __f0(x, lambda y: y ** 7 - y)
            return z
        """
        post_extracted = """
        def __f0(__1, __m1):
            __0 = __1 ** 7
            __2 = __m1(__0)
            return __2
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_rewrite_capturing_a_closed_variable(self):
        code = """
        def f(x):
            __start_extract__
            y = x ** 7
            z = lambda x: {__metavariable__, __m1, y ** 7 - x}
            __end_extract__
            return z
        """
        post_extract_expected = """
        def f(x):
            z = __f0(x, lambda y, x: y ** 7 - x)
            return z
        """
        post_extracted = """
        def __f0(__1, __m1):
            __0 = __1 ** 7
            __2 = lambda __3: __m1(__0, __3)
            return __2
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_multiple_rewrites(self):
        code = """
        def f(x):
            __start_extract__
            y = x ** 7
            z = lambda x: {__metavariable__, __m1, y ** 7} - {__metavariable__, __m2, x}
            __end_extract__
            return z
        """
        post_extract_expected = """
        def f(x):
            z = __f0(x, lambda y: y ** 7, lambda x: x)
            return z
        """
        post_extracted = """
        def __f0(__1, __m1, __m2):
            __0 = __1 ** 7
            __2 = lambda __3: __m1(__0) - __m2(__3)
            return __2
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_rewrite_inside_comprehension(self):
        code = """
        def f(x):
            y = x ** 7
            __start_extract__
            z = [{__metavariable__, __m1, y ** 7 - x} for x in range(10)]
            __end_extract__
            return z
        """
        post_extract_expected = """
        def f(x):
            y = x ** 7
            z = __f0(lambda x: y ** 7 - x)
            return z
        """
        post_extracted = """
        def __f0(__m1):
            __0 = [__m1(__1) for __1 in range(10)]
            return __0
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_rewrite_inside_comprehension(self):
        code = """
        def f(x):
            y = x ** 7
            __start_extract__
            z = [{__metavariable__, __m1, y ** 7 - x} for x in range(10)]
            y = 3
            __end_extract__
            return z
        """
        post_extract_expected = """
        def f(x):
            y = x ** 7
            z = __f0(lambda x: y ** 7 - x)
            return z
        """
        post_extracted = """
        def __f0(__m1):
            __0 = [__m1(__2) for __2 in range(10)]
            __1 = 3
            return __0
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_rewrite_inside_genexpr_extracted_contains_reassign(self):
        code = """
        def f(x):
            y = x ** 7
            __start_extract__
            z = ({__metavariable__, __m1, y ** 7 - x} for x in range(10))
            y = 3
            __end_extract__
            return z
        """
        self.assertEqual(
            self.run_extract(code), ClosureOverVariableModifiedInExtractedCode()
        )

    def test_rewrite_inside_genexpr_extracted_not_contains_reassign(self):
        code = """
        def f(x):
            __start_extract__
            y = x ** 7
            z = ({__metavariable__, __m1, y ** 7 - x} for x in range(10))
            y = 3
            __end_extract__
            return z
        """
        post_extract_expected = """
        def f(x):
            z = __f0(x, lambda y, x: y ** 7 - x)
            return z
        """
        post_extracted = """
        def __f0(__1, __m1):
            __0 = __1 ** 7
            __2 = (__m1(__0, __3) for __3 in range(10))
            __0 = 3
            return __2
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_extract_in_conditional(self):
        code = """
        def _get_content_type(url, session):
            __start_extract__
            if {__metavariable__, __m1, scheme not in ('http', 'https')}:
                return ''
            return 2
            __end_extract__
        """
        post_extract_expected = """
        def _get_content_type(url, session):
            return __f0(lambda: scheme not in ('http', 'https'))
        """
        post_extracted = """
        def __f0(__m1):
            if __m1():
                return ''
            return 2
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_duplicated_metavariable(self):
        code = """
        def f(x):
            __start_extract__
            y = x ** 7
            z = lambda x: {__metavariable__, __m1, y ** 7} - {__metavariable__, __m1, y ** 7}
            __end_extract__
            return z
        """
        post_extract_expected = """
        def f(x):
            z = __f0(x, lambda y: y ** 7)
            return z
        """
        post_extracted = """
        def __f0(__1, __m1):
            __0 = __1 ** 7
            __2 = lambda __3: __m1(__0) - __m1(__0)
            return __2
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_extract_real_001(self):
        code = """
        def f(x, y):
            __start_extract__
            x = x ** 3
            y = x ** 7
            return y ** {__metavariable__, __m1, x - y}
            __end_extract__
        """
        post_extract_expected = """
        def f(x, y):
            return __f0(x, lambda x, y: x - y)
        """
        post_extracted = """
        def __f0(__0, __m1):
            __0 = __0 ** 3
            __1 = __0 ** 7
            return __1 ** __m1(__0, __1)
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )


class ExtractRealisticTest(GenericExtractTest):
    def test_temporary(self):
        try:
            with open("__test__.py") as f:
                code = f.read()
        except FileNotFoundError:
            return
        self.run_extract(code)

    @parameterized.expand([(i,) for i in range(len(small_set_examples()))])
    def test_realistic(self, i):
        rng = np.random.RandomState(i)
        code = small_set_examples()[i]
        tree = ast.parse(code)
        g = control_flow.get_control_flow_graph(tree)
        print(code)
        for entry_point in g.get_enter_blocks():
            print(entry_point)
            if not entry_point.node.body:
                continue
            code, count = self.sample_site(rng, copy.deepcopy(entry_point.node))
            print(code)
            try:
                self.run_extract(code, count)
            except BannedComponentError:
                # don't error on this, just skip it
                pass
            except SyntaxError:
                self.fail()

    def sample_site(self, rng, tree):
        nodes = list(ast_nodes_in_order(tree))
        fields = [
            (n, f)
            for n in nodes
            for f in n._fields
            if field_is_body(type(n), f) and len(getattr(n, f)) > 0
        ]
        node, field = fields[rng.choice(len(fields))]
        length = len(getattr(node, field))
        start = rng.randint(length)
        end = rng.randint(start + 1, length + 1)
        body = getattr(node, field)
        body.insert(start, ast.Expr(ast.Name("__start_extract__")))
        body.insert(end + 1, ast.Expr(ast.Name("__end_extract__")))
        body[start + 1 : end + 1], count = self.manipulate(
            body[start + 1 : end + 1], rng
        )
        return ast.unparse(tree), count

    def manipulate(self, body, rng):
        return body, 0


class RewriteRealisticTest(ExtractRealisticTest):
    def manipulate(self, body, rng):
        expressions = list(
            x for x, state in compute_types_each(body, "S") if state == "E"
        )
        expressions = [
            x for x in expressions if not isinstance(x, (ast.Slice, ast.Ellipsis))
        ]
        if not expressions:
            return body, 0
        count = rng.randint(1, min(5, len(expressions) + 1))
        expressions = sample_non_overlapping(expressions, count, rng)
        print([repr(ast.unparse(e)) for e in expressions])
        replace = ReplaceNodes(
            {
                expr: ast.Set(
                    elts=[ast.Name("__metavariable__"), ast.Name(f"__m{i}"), expr]
                )
                for i, expr in enumerate(expressions)
            }
        )
        body = [replace.visit(stmt) for stmt in body]
        return body, len(expressions)


def sample_non_overlapping(xs, count, rng):
    result = []
    while xs:
        i = rng.randint(len(xs))
        result.append(xs[i])
        xs = xs[:i] + xs[i + 1 :]
        if len(result) == count:
            break
        xs = [x for x in xs if not overlapping(x, result[-1])]
    return result


def overlapping(x, y):
    return set(ast.walk(x)) & set(ast.walk(y))
