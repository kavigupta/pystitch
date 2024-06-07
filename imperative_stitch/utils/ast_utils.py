import ast


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
