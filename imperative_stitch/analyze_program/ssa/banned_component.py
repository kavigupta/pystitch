import ast


class BannedComponentError(Exception):
    pass


class BannedComponentVisitor(ast.NodeVisitor):
    def visit_With(self, node):
        raise BannedComponentError(
            "with statements cannot be used because of a limitation with python-graphs"
        )
