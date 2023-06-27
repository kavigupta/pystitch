from ast import AST
import ast
from dataclasses import dataclass
from functools import cached_property

from python_graphs import control_flow


@dataclass
class ExtractionSite:
    node: AST
    body_field: str
    start: int
    end: int  # exclusive

    @property
    def containing_sequence(self):
        """
        Returns the sequence of statements that contains the extraction site.
        """
        return getattr(self.node, self.body_field)

    def statements(self):
        """
        Returns the statements in the extraction site.
        """
        return self.containing_sequence[self.start : self.end]

    @cached_property
    def all_nodes(self):
        """
        Returns all the nodes in the extraction site.
        """
        return {node for stmt in self.statements() for node in ast.walk(stmt)}

    def locate_entry_point(self, tree):
        """
        Locate the entry point of the extraction site in the tree.
        """
        from imperative_stitch.analyze_program.structures.per_function_cfg import (
            PerFunctionCFG,
        )

        g = control_flow.get_control_flow_graph(tree)
        entry_points = list(g.get_enter_blocks())
        for entry_point in entry_points:
            pfcfg = PerFunctionCFG(entry_point)
            if self.node not in pfcfg.astn_order:
                continue
            return pfcfg
        raise RuntimeError("Not found in given tree")
