import ast
import unittest

from imperative_stitch.analyze_program.extract.loop import replace_break_and_continue

from .utils import canonicalize


class ReplaceBreakAndContinueTest(unittest.TestCase):
    def run_replace(self, code):
        code = canonicalize(code)
        tree = ast.parse(code)
        assert isinstance(tree, ast.Module)
        assert len(tree.body) == 1
        tree = tree.body[0]
        b, c, _, tree, _ = replace_break_and_continue(
            tree, ast.Expr(ast.Name("__replaced__"))
        )
        return b, c, ast.unparse(tree)

    def assertCodes(self, pre_replace, post_replace, b=False, c=False):
        post_replace = canonicalize(post_replace)
        b_ac, c_ac, post_replace_ac = self.run_replace(pre_replace)
        self.assertEqual(b, b_ac)
        self.assertEqual(c, c_ac)
        self.assertEqual(post_replace, post_replace_ac)

    def test_basic(self):
        pre_replace = """
        def f(x):
            break
            continue
            return x
        """
        post_replace = """
        def f(x):
            __replaced__
            __replaced__
            return x
        """
        self.assertCodes(pre_replace, post_replace, b=True, c=True)

    def test_in_loop(self):
        pre_replace = """
        def f(x):
            while True:
                break
                continue
                return x
        """
        post_replace = """
        def f(x):
            while True:
                break
                continue
                return x
        """
        self.assertCodes(pre_replace, post_replace)

    def test_inner_function(self):
        pre_replace = """
        def f(x):
            def g():
                break
                continue
                return x
            return g()
        """
        post_replace = """
        def f(x):
            def g():
                break
                continue
                return x
            return g()
        """
        self.assertCodes(pre_replace, post_replace)

    def test_both_in_loop_and_out(self):
        pre_replace = """
        def f(x):
            break
            while True:
                continue
                return x
        """
        post_replace = """
        def f(x):
            __replaced__
            while True:
                continue
                return x
        """
        self.assertCodes(pre_replace, post_replace, b=True)

    def test_inside_else(self):
        pre_replace = """
        def f(x):
            break
            while True:
                continue
                return x
            else:
                continue
        """
        post_replace = """
        def f(x):
            __replaced__
            while True:
                continue
                return x
            else:
                __replaced__
        """
        self.assertCodes(pre_replace, post_replace, b=True, c=True)
