import ast
from dataclasses import dataclass


@dataclass(eq=True)
class BannedComponentError(Exception):
    component_type: str
    at_fault: ast.AST


class BannedComponentVisitor(ast.NodeVisitor):

    def visit_ClassDef(self, node):
        raise BannedComponentError("classes", "us")

    def visit_Nonlocal(self, node):
        raise BannedComponentError("nonlocal", "us")

    def visit_NamedExpr(self, node):
        raise BannedComponentError("walrus operator", "us")

    def visit_Yield(self, node):
        raise BannedComponentError("yield", "us")

    def visit_YieldFrom(self, node):
        raise BannedComponentError("yield from", "us")

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
