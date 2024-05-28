import ast
import uuid

import ast_scope
import neurosym as ns

from .wrap import wrap_ast


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


def true_globals(node):
    name = "_" + uuid.uuid4().hex
    wpd = wrap_ast(node, name)
    scope_info = ast_scope.annotate(wpd)
    return {
        x
        for x in scope_info
        if scope_info[x] == scope_info.global_scope
        if getattr(x, ns.python_ast_tools.name_field(x)) != name
    }
