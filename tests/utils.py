import ast
import inspect
import json
from functools import lru_cache
from textwrap import dedent

import pytest
from parameterized import parameterized


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

def cwq(s):
    """
    Canonicalize with question marks and dollars
    """
    s = dedent(s)
    s = s.replace("?", "__QUESTION__MARK__")
    s = s.replace("$", "__DOLLAR__")
    s = ast.unparse(ast.parse(s))
    s = s.replace("__QUESTION__MARK__", "?")
    s = s.replace("__DOLLAR__", "$")
    return s