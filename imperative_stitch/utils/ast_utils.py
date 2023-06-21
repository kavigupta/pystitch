import ast

from ast_scope.annotator import name_of_alias


def field_is_body(t, f):
    assert isinstance(t, type)
    if t == ast.IfExp:
        return False  # not body of statements
    if t == ast.Lambda:
        return False  # not body of statements
    return f in {"body", "orelse", "finalbody"}


def name_field(x):
    t = type(x)
    if t == ast.Name:
        return "id"
    if t == ast.arg:
        return "arg"
    if t == ast.FunctionDef:
        return "name"
    if t == ast.AsyncFunctionDef:
        return "name"
    if t == ast.ExceptHandler:
        return "name"
    if t == ast.ClassDef:
        return "name"
    if t == ast.alias:
        return name_of_alias(x)
    raise Exception(f"Unexpected type: {t}")


class AstNodesInOrder(ast.NodeVisitor):
    def __init__(self):
        self.nodes = []

    def visit(self, node):
        self.nodes.append(node)
        super().visit(node)


def ast_nodes_in_order(node):
    visitor = AstNodesInOrder()
    visitor.visit(node)
    return visitor.nodes
