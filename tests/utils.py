import ast
from functools import lru_cache
import json
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
