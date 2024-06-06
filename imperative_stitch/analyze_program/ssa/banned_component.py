import ast
from dataclasses import dataclass


class ParentOfVisitor(ast.NodeVisitor):
    def __init__(self):
        self.parent_of = {}

    def visit(self, node):
        if not hasattr(node, "_fields"):
            return
        for f in node._fields:
            res = getattr(node, f)
            if isinstance(res, list):
                for x in res:
                    self.parent_of[x] = node
            else:
                self.parent_of[res] = node
        super().generic_visit(node)


@dataclass(eq=True)
class BannedComponentError(Exception):
    component_type: str
    at_fault: ast.AST


class BannedComponentVisitor(ast.NodeVisitor):
    def __init__(self, parent_of):
        self.parent_of = parent_of

    def visit_ClassDef(self, node):
        raise BannedComponentError("classes", "us")

    def visit_Nonlocal(self, node):
        raise BannedComponentError("nonlocal", "us")

    def visit_NamedExpr(self, node):
        raise BannedComponentError("walrus operator", "us")

    def visit_AsyncFor(self, node):
        raise BannedComponentError("async for", "us")

    def visit_AsyncWith(self, node):
        raise BannedComponentError("async with", "us")

    def visit_AsyncFunctionDef(self, node):
        raise BannedComponentError("async functions", "us")

    def visit_Await(self, node):
        raise BannedComponentError("await", "us")

    def visit_Global(self, node):
        raise BannedComponentError("global", "us")

    def visit_Yield(self, node):
        self.check_not_coroutine(node)

    def visit_YieldFrom(self, node):
        self.check_not_coroutine(node)

    def check_not_coroutine(self, node):
        if not isinstance(self.parent_of[node], (ast.Expr, ast.Lambda)):
            raise BannedComponentError("coroutine", "us")


def check_banned_components(node):
    parents = ParentOfVisitor()
    parents.visit(node)
    BannedComponentVisitor(parents.parent_of).visit(node)
