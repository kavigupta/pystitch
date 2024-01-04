"""
There are three representations of a python program.

    1. actual python code, as a string. E.g., "x = 2"
    2. the ParsedAST representation we use
    3. s-expressions for stitch. E.g., "(Assign (list (Name &x:0 Store)) (Constant i2 None) None)"
"""

import ast
from s_expression_parser import Renderer

from imperative_stitch.parser.parsed_ast import ParsedAST
from imperative_stitch.utils.recursion import recursionlimit


def python_to_s_exp(code, renderer_kwargs=None):
    if renderer_kwargs is None:
        renderer_kwargs = {}
    with recursionlimit(max(1500, len(code))):
        code = ParsedAST.parse_python_code(code)
        code = code.to_pair_s_exp()
        code = Renderer(**renderer_kwargs, nil_as_word=True).render(code)
        return code


def s_exp_to_python(code):
    with recursionlimit(max(1500, len(code))):
        code = ParsedAST.parse_s_expression(code)
        code = code.to_python_ast()
        code = ast.unparse(code)
        return code
