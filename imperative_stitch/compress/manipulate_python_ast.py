import ast

import neurosym as ns

from imperative_stitch.parser import converter
from imperative_stitch.parser.python_ast import LeafAST, ListAST, NodeAST, SequenceAST


def render_symvar(node):
    """
    Render this PythonAST as a __ref__ variable for stub display, i.e.,
        `a` -> `__ref__(a)`
    """
    return ns.make_python_ast.make_call(
        ns.PythonSymbol(name="__ref__", scope=None), ns.make_python_ast.make_name(node)
    )


def render_codevar(node):
    """
    Render this PythonAST as a __code__ variable for stub display, i.e.,
        `a` -> `__code__("a")`
    """
    return ns.make_python_ast.make_call(
        ns.PythonSymbol(name="__code__", scope=None),
        ns.make_python_ast.make_constant(node.to_python()),
    )


def wrap_in_metavariable(node, name):
    return NodeAST(
        ast.Set,
        [
            ListAST(
                [
                    ns.make_python_ast.make_name(
                        LeafAST(ns.PythonSymbol("__metavariable__", None))
                    ),
                    ns.make_python_ast.make_name(LeafAST(ns.PythonSymbol(name, None))),
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
