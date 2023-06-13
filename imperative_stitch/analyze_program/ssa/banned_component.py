import ast


class BannedComponentError(Exception):
    pass


class BannedComponentVisitor(ast.NodeVisitor):
    def visit_With(self, node):
        raise BannedComponentError(
            "with statements cannot be used because of a limitation with python-graphs"
        )

    def visit_ClassDef(self, node):
        raise BannedComponentError(
            "inner classes cannot be used because we do not support them yet"
        )
