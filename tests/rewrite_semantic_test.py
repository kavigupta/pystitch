import ast

from parameterized import parameterized

from imperative_stitch.utils.run_code import normalize_output, run_python
from tests.rewrite_test import GenericRewriteRealisticTest

from .utils import small_set_runnable_code_examples


class RewriteSemanticsTest(GenericRewriteRealisticTest):
    @parameterized.expand(
        [(i,) for i in range(5 * len(small_set_runnable_code_examples()))]
    )
    def test_semantics(self, i):
        example = small_set_runnable_code_examples()[
            i % len(small_set_runnable_code_examples())
        ]
        code_original = example["solution"]
        xs = self.operate_on_code(i, code_original, use_full_tree=True)
        for code, out in xs:
            if isinstance(out, Exception):
                continue
            post_extract, extracted = out
            new_code = self.concat_code(extracted, post_extract)
            print("*" * 80)
            print(code)
            print("=" * 80)
            print(new_code)
            for input, output in zip(example["inputs"], example["outputs"]):
                print(repr(input))
                py_out = run_python(new_code, input)
                if py_out is None:
                    run_python.function(new_code, input)
                    self.fail("error")
                py_out = normalize_output(py_out)
                output = normalize_output(output)
                if py_out != output:
                    if not self.check_deterministic(code_original, input):
                        continue
                self.assertEqual(py_out, output)

    def check_deterministic(self, code, input):
        outputs = []
        for i in range(20):
            outputs.append(run_python.function(code, input))
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
