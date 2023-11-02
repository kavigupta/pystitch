import ast
import json
from functools import lru_cache
from textwrap import dedent


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
