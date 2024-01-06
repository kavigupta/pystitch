import ast

from s_expression_parser import Renderer

from imperative_stitch.parser.parsed_ast import ParsedAST
from imperative_stitch.utils.recursion import limit_to_size


def python_to_s_exp(code, renderer_kwargs=None):
    """
    Converts python code to an s-expression.
    """
    if renderer_kwargs is None:
        renderer_kwargs = {}
    with limit_to_size(code):
        code = ParsedAST.parse_python_code(code)
        code = code.to_pair_s_exp()
        code = Renderer(**renderer_kwargs, nil_as_word=True).render(code)
        return code


def s_exp_to_python(code):
    """
    Converts an s expression to python code.
    """
    with limit_to_size(code):
        code = ParsedAST.parse_s_expression(code)
        code = code.to_python_ast()
        code = ast.unparse(code)
        return code
