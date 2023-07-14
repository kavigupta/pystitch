from ast import AST
import ast
from dataclasses import dataclass

from python_graphs import control_flow

from imperative_stitch.utils.ast_utils import ReplaceNodes


@dataclass
class ExtractionSite:
    node: AST
    body_field: str
    start: int
    end: int  # exclusive
    metavariables: list[tuple[str, ast.AST]]
    sentinel: ast.AST = None

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

    @property
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
        pfcfgs = []
        for entry_point in list(g.get_enter_blocks()):
            pfcfg = PerFunctionCFG(entry_point)
            if self.node not in pfcfg.astn_order:
                continue
            pfcfgs.append(pfcfg)
        if not pfcfgs:
            raise RuntimeError("Not found in given tree")
        # get the entry point with the fewest nodes, that is the
        # innermost function containing the site
        return min(pfcfgs, key=lambda x: len(x.astn_order))

    def add_pragmas(self):
        """
        Manipulate the AST to put the extraction site pragmas back in.
        """
        body = self.containing_sequence
        body.insert(self.start, ast.parse("__start_extract__").body[0])
        body.insert(self.end + 1, ast.parse("__end_extract__").body[0])
        ReplaceNodes(
            {
                node: ast.Set(elts=[ast.Name("__metavariable__"), ast.Name(name), node])
                for name, node in self.metavariables
            }
        ).visit(self.node)

    def inject_sentinel(self):
        """
        Inject a sentinel to mark the start of the extraction site.
        """
        assert self.sentinel is None
        body = self.containing_sequence
        self.sentinel = [
            ast.parse(pragma).body[0]
            for pragma in ("'__start_sentinel_before__'", "'__start_sentinel_inside__'")
        ]
        body.insert(self.start, self.sentinel[1])
        body.insert(self.start, self.sentinel[0])
        self.start += 1
        self.end += 2
        return lambda: self._remove_sentinel(self.sentinel)

    def _remove_sentinel(self, sentinel):
        """
        Remove the sentinel from the AST.
        """
        assert self.sentinel is sentinel
        body = self.containing_sequence
        self.start -= 1
        assert body.pop(self.start) is sentinel[0]
        assert body.pop(self.start) is sentinel[1]
        self.end -= 2
        self.sentinel = None
