from ast import AST
import ast
from dataclasses import dataclass
from functools import cached_property


@dataclass
class ExtractionSite:
    node: AST
    body_field: str
    start: int
    end: int  # exclusive

    def statements(self):
        """
        Returns the statements in the extraction site.
        """
        return getattr(self.node, self.body_field)[self.start : self.end]

    @cached_property
    def all_nodes(self):
        """
        Returns all the nodes in the extraction site.
        """
        return {node for stmt in self.statements() for node in ast.walk(stmt)}
