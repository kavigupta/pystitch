import ast

from imperative_stitch.parser import converter
from imperative_stitch.parser.python_ast import (
    LeafAST,
    ListAST,
    NodeAST,
    PythonAST,
    SequenceAST,
)
from imperative_stitch.parser.symbol import PythonSymbol


def render_symvar(node):
    """
    Render this PythonAST as a __ref__ variable for stub display, i.e.,
        `a` -> `__ref__(a)`
    """
    return make_call(PythonSymbol(name="__ref__", scope=None), make_name(node))


def render_codevar(node):
    """
    Render this PythonAST as a __code__ variable for stub display, i.e.,
        `a` -> `__code__("a")`
    """
    return make_call(
        PythonSymbol(name="__code__", scope=None),
        make_constant(node.to_python()),
    )


def wrap_in_metavariable(node, name):
    return NodeAST(
        ast.Set,
        [
            ListAST(
                [
                    make_name(LeafAST(PythonSymbol("__metavariable__", None))),
                    make_name(LeafAST(PythonSymbol(name, None))),
                    node,
                ]
            )
        ],
    )


def wrap_in_choicevar(node):
    return SequenceAST(
        "/seq",
        [
            converter.python_statement_to_python_ast("__start_choice__"),
            node,
            converter.python_statement_to_python_ast("__end_choice__"),
        ],
    )


def make_constant(leaf):
    """
    Create a constant PythonAST from the given leaf value (which must be a python constant).
    """
    assert not isinstance(leaf, PythonAST), leaf
    return NodeAST(typ=ast.Constant, children=[LeafAST(leaf=leaf), LeafAST(leaf=None)])


def make_name(name_node):
    """
    Create a name PythonAST from the given name node containing a symbol.
    """
    assert isinstance(name_node, LeafAST) and isinstance(
        name_node.leaf, PythonSymbol
    ), name_node
    return NodeAST(
        typ=ast.Name,
        children=[
            name_node,
            NodeAST(typ=ast.Load, children=[]),
        ],
    )


def make_call(name_sym, *arguments):
    """
    Create a call PythonAST from the given symbol and arguments.

    In this case, the symbol must be a symbol representing a name.
    """
    assert isinstance(name_sym, PythonSymbol), name_sym
    return NodeAST(
        typ=ast.Call,
        children=[
            make_name(LeafAST(name_sym)),
            ListAST(children=arguments),
            ListAST(children=[]),
        ],
    )


def make_expr_stmt(expr):
    """
    Create an expression statement PythonAST from the given expression.
    """
    return NodeAST(typ=ast.Expr, children=[expr])
