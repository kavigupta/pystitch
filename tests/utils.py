import ast
from textwrap import dedent


def canonicalize(code):
    code = dedent(code)
    code = ast.unparse(ast.parse(code))
    return code
