import ast
import copy

from imperative_stitch.utils.ast_utils import ReplaceNodes


def replace_break_and_continue(function_def, replace_with):
    """
    Replace top-level break and continue statements with the given statement.
    Do *not* replace break and continue statements inside loops or inner functions.

    Args:
        function_def (ast.FunctionDef): The function definition to modify.
        replace_with (ast.AST): The AST node to replace break and continue statements with.

    Returns:
        has_break: True if the function contained a break statement.
        has_continue: True if the function contained a continue statement.
        returns: List of the return statements added
        ast.FunctionDef: The modified function definition.
        undo: A function that will undo the replacement.
    """
    assert isinstance(function_def, ast.FunctionDef), function_def
    transformer = ReplaceBreakAndContinue(replace_with)
    function_def.body = [transformer.visit(x) for x in function_def.body]
    return (
        transformer.has_break,
        transformer.has_continue,
        list(transformer.replace_back.keys()),
        function_def,
        lambda: ReplaceNodes(transformer.replace_back).visit(function_def),
    )


class ReplaceBreakAndContinue(ast.NodeTransformer):
    """Replace break and continue statements with the given statement.

    Attributes:
        has_break (bool): True if the function contained a break statement.
        has_continue (bool): True if the function contained a continue statement.
    """

    def __init__(self, replace_with):
        super().__init__()
        self.replace_with = replace_with
        self.has_break = False
        self.has_continue = False
        self.replace_back = {}

    def replace_node(self, node):
        replace_with = copy.deepcopy(self.replace_with)
        self.replace_back[replace_with] = node
        return replace_with

    def visit_Break(self, node):
        self.has_break = True
        return self.replace_node(node)

    def visit_Continue(self, node):
        self.has_continue = True
        return self.replace_node(node)

    def visit_FunctionDef(self, node):
        return node

    def visit_While(self, node):
        node.orelse = self.visit_all(node.orelse)
        return node

    def visit_For(self, node):
        node.orelse = self.visit_all(node.orelse)
        return node

    def visit_all(self, nodes):
        return [self.visit(node) for node in nodes]
