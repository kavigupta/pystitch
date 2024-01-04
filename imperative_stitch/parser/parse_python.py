import ast

from imperative_stitch.parser.parsed_ast import (
    LeafAST,
    ListAST,
    NodeAST,
    SequenceAST,
)
from imperative_stitch.utils.ast_utils import field_is_body, name_field

from .symbol import Symbol


def python_ast_to_parsed_ast(x, descoper, is_body=False):
    if is_body:
        assert isinstance(x, list), str(x)
        x = [python_ast_to_parsed_ast(x, descoper) for x in x]
        return SequenceAST("/seq", x)
    if isinstance(x, ast.AST):
        result = []
        for f in x._fields:
            el = getattr(x, f)
            if x in descoper and f == name_field(x):
                assert isinstance(el, str), (x, f, el)
                result.append(LeafAST(Symbol(el, descoper[x])))
            else:
                result.append(
                    python_ast_to_parsed_ast(
                        el, descoper, is_body=field_is_body(type(x), f)
                    )
                )
        return NodeAST(type(x), result)
    if isinstance(x, list):
        return ListAST([python_ast_to_parsed_ast(x, descoper) for x in x])
    if x is None or x is Ellipsis or isinstance(x, (int, float, complex, str, bytes)):
        return LeafAST(x)
    raise ValueError(f"Unsupported node {x}")
