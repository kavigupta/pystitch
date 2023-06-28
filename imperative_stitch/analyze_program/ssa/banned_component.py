import ast


class BannedComponentError(Exception):
    def __eq__(self, other):
        return isinstance(other, BannedComponentError) and self.args == other.args


class BannedComponentVisitor(ast.NodeVisitor):
    def visit_With(self, node):
        raise BannedComponentError(
            "with statements cannot be used because of a limitation with python-graphs"
        )

    def visit_ClassDef(self, node):
        raise BannedComponentError(
            "inner classes cannot be used because we do not support them yet"
        )

    def visit_Nonlocal(self, node):
        raise BannedComponentError(
            "nonlocal statements cannot be used because we do not support them yet"
        )

    def visit_NamedExpr(self, node):
        raise BannedComponentError(
            "walrus statements cannot be used because we do not support them yet"
        )
