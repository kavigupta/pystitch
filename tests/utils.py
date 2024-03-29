import ast
import copy
import inspect
import json
from functools import lru_cache
from textwrap import dedent

import pytest
from parameterized import parameterized

from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.data.stitch_output_set import load_annies_compressed_dataset
from imperative_stitch.parser.parsed_ast import ParsedAST


def canonicalize(code):
    code = dedent(code)
    code = ast.unparse(ast.parse(code))
    return code


@lru_cache(None)
def small_set_examples():
    with open("data/small_set.json") as f:
        contents = json.load(f)
    return contents


@lru_cache(None)
def small_set_runnable_code_examples():
    with open("data/small_set_runnable_code.json") as f:
        contents = json.load(f)
    return contents


def expand_with_slow_tests(count, first_fast=10):
    namespace = inspect.currentframe().f_back.f_locals
    # return lambda f: parameterized.expand([(i,) for i in range(first_fast)], )(f)

    def annotation(f):
        parameterized.expand([(i,) for i in range(count)], namespace=namespace)(f)

        name = f.__name__
        for k in list(namespace.keys()):
            if k.startswith(name + "_"):
                idx = int(k[len(name + "_") :])
                if idx > first_fast:
                    namespace[k] = pytest.mark.slow_test(namespace[k])

    return annotation


def assertDSL(test_obj, dsl, expected):
    dsl = "\n".join(sorted([line.strip() for line in dsl.split("\n") if line.strip()]))
    expected = "\n".join(
        sorted([line.strip() for line in expected.split("\n") if line.strip()])
    )
    print(dsl)
    test_obj.maxDiff = None
    test_obj.assertEqual(dsl, expected)


@lru_cache(None)
def load_annies_compressed_individual_programs():
    dat = copy.deepcopy(load_annies_compressed_dataset())
    result = []
    for key in sorted(dat.keys()):
        x = dat[key]
        abstrs = x["abstractions"]
        rewrs = x["rewritten"]
        for it, abstr in enumerate(abstrs):
            abstr["body"] = ParsedAST.parse_s_expression(abstr["body"])
            abstrs[it] = Abstraction(name=f"fn_{it + 1}", **abstr)
        for rewritten in rewrs:
            result.append((abstrs, rewritten))
    return result
