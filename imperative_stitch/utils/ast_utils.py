import ast


def field_is_body(t, f):
    assert isinstance(t, type)
    if t == ast.IfExp:
        return False  # not body of statements
    if t == ast.Lambda:
        return False  # not body of statements
    return f in {"body", "orelse", "finalbody"}


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
