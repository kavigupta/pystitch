import ast


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
        return "name" if x.name is not None else None
    if t == ast.ClassDef:
        return "name"
    if t == ast.alias:
        if x.asname is None:
            return "name"
        return "asname"
    raise NotImplementedError(f"Unexpected type: {t}")


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


class ReplaceNodes(ast.NodeTransformer):
    def __init__(self, node_map):
        super().__init__()
        self.node_map = node_map

    def visit(self, node):
        if node in self.node_map:
            return self.node_map[node]
        return super().visit(node)
