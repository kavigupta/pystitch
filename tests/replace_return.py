import ast
import unittest

from imperative_stitch.analyze_program.extract import remove_unnecessary_returns

from .utils import canonicalize


class RemoveUnnecessaryReturnsTest(unittest.TestCase):
    def run_remove(self, code):
        code = canonicalize(code)
        tree = ast.parse(code)
        assert isinstance(tree, ast.Module)
        assert len(tree.body) == 1
        tree = tree.body[0]
        tree = remove_unnecessary_returns(tree)
        return ast.unparse(tree)

    def assertCode(self, pre_remove, post_remove):
        post_remove = canonicalize(post_remove)
        post_replace_ac = self.run_remove(pre_remove)
        self.assertEqual(post_remove, post_replace_ac)

    def test_then_empty(self):
        pre_remove = """
        def f(x):
            return
        """
        post_remove = """
        def f(x):
            pass
        """
        self.assertCode(pre_remove, post_remove)

    def test_non_empty(self):
        pre_remove = """
        def f(x):
            x = 2
            return
        """
        post_remove = """
        def f(x):
            x = 2
        """
        self.assertCode(pre_remove, post_remove)

    def test_necessary_return_at_end(self):
        pre_remove = """
        def f(x):
            return x
        """
        post_remove = """
        def f(x):
            return x
        """
        self.assertCode(pre_remove, post_remove)

    def test_blank_return_not_at_end(self):
        pre_remove = """
        def f(x):
            return
            x = 2
        """
        post_remove = """
        def f(x):
            return
            x = 2
        """
        self.assertCode(pre_remove, post_remove)

    def test_dead_return_sequence(self):
        pre_remove = """
        def f(x):
            return 2
            return x
        """
        post_remove = """
        def f(x):
            return 2
        """
        self.assertCode(pre_remove, post_remove)

    def test_dead_return_sequence_post_if(self):
        pre_remove = """
        def f(x):
            if x > 0:
                return 2
            else:
                return x
            return 3
        """
        post_remove = """
        def f(x):
            if x > 0:
                return 2
            else:
                return x
        """
        self.assertCode(pre_remove, post_remove)
