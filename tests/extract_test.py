import ast
import copy
import unittest
import numpy as np
from parameterized import parameterized

from imperative_stitch.analyze_program.extract.errors import (
    ClosedVariablePassedDirectly,
    ClosureOverVariableModifiedInExtractedCode,
    MultipleExits,
    NonInitializedInputsOrOutputs,
)
from imperative_stitch.analyze_program.ssa.banned_component import BannedComponentError

from imperative_stitch.data import parse_extract_pragma
from imperative_stitch.analyze_program.extract import do_extract
from imperative_stitch.analyze_program.extract import NotApplicable
from imperative_stitch.utils.ast_utils import (
    ast_nodes_in_order,
    field_is_body,
)
from python_graphs import control_flow

from tests.utils import canonicalize, small_set_examples


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
            print(type(e), e)
            self.maxDiff = None
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
            return __f0()
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

    def test_augadd_const(self):
        code = """
        def f(x, y):
            __start_extract__
            x += 1
            __end_extract__
            return x
        """
        post_extract_expected = """
        def f(x, y):
            x = __f0(x)
            return x
        """
        post_extracted = """
        def __f0(__0):
            __0 += 1
            return __0
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_augadd_inside_function(self):
        code = """
        def f(x, y):
            def g(x):
                __start_extract__
                x += 1
                __end_extract__
            return x
        """
        post_extract_expected = """
        def f(x, y):
            def g(x):
                return __f0(x)
            return x
        """
        post_extracted = """
        def __f0(__0):
            __0 += 1
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
        self.assertEqual(self.run_extract(code), NonInitializedInputsOrOutputs())

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
        self.assertEqual(self.run_extract(code), NonInitializedInputsOrOutputs())

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
        post_extract_expected = """
        def _main(i):
            count = 2
            count = __f0(i, count)
            return count
        """
        post_extracted = """
        def __f0(__0, __1):
            if __0 == '8':
                __1 = 7
            return __1
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_capturing_from_parent(self):
        code = """
        def f():
            func = 2
            def g():
                __start_extract__
                func()
                __end_extract__
            return g
        """
        post_extract_expected = """
        def f():
            func = 2
            def g():
                return __f0(func)
            return g
        """
        post_extracted = """
        def __f0(__0):
            __0()
        """
        self.assertCodes(
            self.run_extract(code), (post_extract_expected, post_extracted)
        )

    def test_exception_multiple_exits_INCORRECT_TODO(self):
        code = """
        def test_3118(self):

            def gen():
                try:
                    yield 1
                finally:
                    pass

            def f():
                g = gen()
                next(g)
                try:
                    __start_extract__
                    2
                    try:
                        raise {__metavariable__, __m0, ValueError}
                    except:
                        del g
                        raise KeyError
                    __end_extract__
                except Exception as e:
                    self.assertIsInstance(e.__context__, ValueError)
            f()
        """
        # TODO this is not the correct output
        # It results from a bug in python_graphs that we should fix
        self.assertEqual(self.run_extract(code), MultipleExits())


class GenericExtractRealisticTest(GenericExtractTest):
    def test_temporary(self):
        try:
            with open("__test__.py") as f:
                code = f.read()
        except FileNotFoundError:
            return
        self.run_extract(code)

    def operate(self, i, use_full_tree=False):
        code = small_set_examples()[i]
        return self.operate_on_code(i, code, use_full_tree=use_full_tree)

    def operate_on_code(self, i, full_code, use_full_tree=False):
        rng = np.random.RandomState(i)
        tree = ast.parse(full_code)
        g = control_flow.get_control_flow_graph(tree)
        num_entry_points = len(list(g.get_enter_blocks()))
        print(full_code)
        result = []
        for i in range(num_entry_points):
            tree = ast.parse(full_code)
            g = control_flow.get_control_flow_graph(tree)
            entry_point = list(g.get_enter_blocks())[i]
            print(entry_point)
            if not entry_point.node.body:
                continue
            code, count = self.sample_site(rng, entry_point.node)
            if use_full_tree:
                code = ast.unparse(tree)
            print(code)
            try:
                out = self.run_extract(code, count)
                result.append((code, out))
            except (NotApplicable, BannedComponentError):
                # don't error on this, just skip it
                pass
            except SyntaxError:
                self.fail()
        return result

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


class ExtractRealisticTest(GenericExtractRealisticTest):
    @parameterized.expand([(i,) for i in range(len(small_set_examples()))])
    def test_realistic(self, i):
        self.operate(i)
