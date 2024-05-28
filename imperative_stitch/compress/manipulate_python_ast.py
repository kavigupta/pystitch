import ast

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
    return PythonAST.call(
        PythonSymbol(name="__ref__", scope=None), PythonAST.name(node)
    )


def render_codevar(node):
    """
    Render this PythonAST as a __code__ variable for stub display, i.e.,
        `a` -> `__code__("a")`
    """
    return PythonAST.call(
        PythonSymbol(name="__code__", scope=None),
        PythonAST.constant(node.to_python()),
    )


def wrap_in_metavariable(node, name):
    return NodeAST(
        ast.Set,
        [
            ListAST(
                [
                    PythonAST.name(LeafAST(PythonSymbol("__metavariable__", None))),
                    PythonAST.name(LeafAST(PythonSymbol(name, None))),
                    node,
                ]
            )
        ],
    )


def wrap_in_choicevar(node):
    return SequenceAST(
        "/seq",
        [
            PythonAST.parse_python_statement("__start_choice__"),
            node,
            PythonAST.parse_python_statement("__end_choice__"),
        ],
    )
