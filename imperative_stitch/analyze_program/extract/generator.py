import ast


class CheckIfGenerator(ast.NodeVisitor):
    def __init__(self):
        self.is_generator = False

    def visit_list(self, nodes):
        assert isinstance(nodes, list)
        for node in nodes:
            self.visit(node)

    def visit_Yield(self, node):
        self.is_generator = True

    def visit_YieldFrom(self, node):
        self.is_generator = True

    def visit_FunctionDef(self, node):
        self.visit(node.args)
        self.visit_list(node.decorator_list)

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_Lambda(self, node):
        self.visit(node.args)


def is_function_generator(func_node):
    generator = CheckIfGenerator()
    generator.visit_list(func_node.body)
    return generator.is_generator
