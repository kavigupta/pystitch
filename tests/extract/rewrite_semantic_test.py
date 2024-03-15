import ast

from permacache import stable_hash

from imperative_stitch.utils.run_code import normalize_output, run_python
from .rewrite_test import GenericRewriteRealisticTest

from ..utils import expand_with_slow_tests, small_set_runnable_code_examples

TEST_VERSION = 1


class RewriteSemanticsTest(GenericRewriteRealisticTest):
    @expand_with_slow_tests(5 * len(small_set_runnable_code_examples()))
    def test_semantics(self, i):
        example = small_set_runnable_code_examples()[
            i % len(small_set_runnable_code_examples())
        ]
        code_original = example["solution"]
        seed = int(stable_hash((i, TEST_VERSION)), 16) % 2**32
        xs = self.operate_on_code(seed, code_original, use_full_tree=True)
        for code, out in xs:
            if isinstance(out, Exception):
                return
            print("*" * 80)
            print(code)
            post_extract, extracted = out
            self.assert_code_same(example, code_original, post_extract, extracted)

    def assert_code_same(self, example, code_original, post_extract, extracted):
        new_code = self.concat_code(extracted, post_extract)
        print("=" * 80)
        print(new_code)

        for inp, output in zip(example["inputs"], example["outputs"]):
            print(repr(inp))
            py_out = self.run_and_check_for_errors(new_code, inp)
            py_out = normalize_output(py_out)
            output = normalize_output(output)
            if py_out != output:
                if not self.check_deterministic(code_original, inp):
                    continue
            self.assertEqual(py_out, output)

    def run_and_check_for_errors(self, code, inp):
        py_out = run_python(code, inp)
        if py_out is not None:
            return py_out
        code = self.add_header(code)
        py_out = run_python(code, inp)
        if py_out is not None:
            return py_out
        run_python.function(code, inp)
        self.fail("error")
        return None

    def add_header(self, code):
        recursion_header = ast.parse(
            "import sys; sys.setrecursionlimit(10 ** 8); sys.setrecursionlimit = lambda x: None"
        )
        code = ast.parse(code)
        code.body = recursion_header.body + code.body
        code = ast.fix_missing_locations(code)
        return ast.unparse(code)

    def check_deterministic(self, code, inp):
        outputs = []
        for _ in range(20):
            outputs.append(run_python.function(code, inp))
        outputs = set(outputs)
        return len(outputs) == 1

    def concat_code(self, first, second):
        """
        yanks from __future__ import annotations from second
        and then concatenates the two
        """
        second = ast.parse(second)
        first = ast.parse(first)
        future_statements = [
            x
            for x in second.body
            if isinstance(x, ast.ImportFrom) and x.module == "__future__"
        ]
        second.body = (
            future_statements + first.body + second.body[len(future_statements) :]
        )
        second = ast.fix_missing_locations(second)
        return ast.unparse(second)
