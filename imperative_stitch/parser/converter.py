import ast
from types import NoneType
from typing import Union

import neurosym as ns
from increase_recursionlimit import increase_recursionlimit

from imperative_stitch.parser.symbol import create_descoper

from .parse_python import python_ast_to_parsed_ast
from .parse_s_exp import s_exp_to_parsed_ast
from .python_ast import NodeAST, PythonAST, SequenceAST


def python_to_s_exp(code: Union[str, ast.AST], **kwargs) -> str:
    """
    Converts python code to an s-expression.
    """
    return ns.render_s_expression(python_to_python_ast(code).to_ns_s_exp(kwargs))


def s_exp_to_python(code: Union[str, ns.SExpression]) -> str:
    """
    Converts an s expression to python code.
    """
    return s_exp_to_python_ast(code).to_python()


def s_exp_to_python_ast(code: Union[str, ns.SExpression]) -> PythonAST:
    """
    Converts an s expression to a PythonAST object. If the code is a string, it is first parsed into an s-expression.
    """
    with increase_recursionlimit():
        if isinstance(code, str):
            code = ns.parse_s_expression(code)
        code = s_exp_to_parsed_ast(code)
        return code


def python_statement_to_python_ast(code: Union[str, ast.AST]) -> PythonAST:
    """
    Like python_to_python_ast, but for a single statement.
    """
    code = python_statements_to_python_ast(code)
    assert (
        len(code.elements) == 1
    ), f"expected only one statement; got: [{[x.to_python() for x in code.elements]}]]"
    code = code.elements[0]
    return code


def python_statements_to_python_ast(code: Union[str, ast.AST]) -> SequenceAST:
    """
    Like python_to_python_ast, but for a sequence of statements.
    """
    code = python_to_python_ast(code)
    assert isinstance(code, NodeAST) and code.typ is ast.Module
    assert len(code.children) == 2
    code = code.children[0]
    assert isinstance(code, SequenceAST), code
    return code


def python_to_python_ast(
    code: Union[str, ast.AST], descoper: Union[NoneType, dict] = None
) -> PythonAST:
    """
    Parse the given python code into a PythonAST. If the code is a string, it is first parsed into an AST.

    Args:
        code: The python code to parse.
        descoper: The descoper to use. If None, a new one is created.

    Returns:
        The parsed PythonAST.
    """

    with increase_recursionlimit():
        if isinstance(code, str):
            code = ast.parse(code)
        code = python_ast_to_parsed_ast(
            code,
            descoper if descoper is not None else create_descoper(code),
        )
        return code
