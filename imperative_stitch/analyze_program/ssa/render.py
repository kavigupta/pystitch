from _ast import AST
import ast
import copy

from imperative_stitch.analyze_program.ssa.ivm import Phi
from imperative_stitch.utils.non_mutating_node_transformer import (
    NonMutatingNodeTransformer,
)


class RenameVariablesInTree(NonMutatingNodeTransformer):
    def __init__(self, renamed_variables):
        super().__init__()
        self.renamed_variables = renamed_variables

    def visit_Name(self, astn):
        return self.create_new_element(astn)

    def visit_arg(self, astn):
        return self.create_new_element(astn)

    def create_new_element(self, astn):
        # generalize the above two
        if astn in self.renamed_variables:
            astn_copy = copy.deepcopy(astn)
            if isinstance(astn, ast.Name):
                astn_copy.id = self.renamed_variables[astn]
            elif isinstance(astn, ast.arg):
                astn_copy.arg = self.renamed_variables[astn]
            else:
                raise ValueError(f"Unsupported node {astn}")
            return astn_copy
        return astn


def rename_to_ssa(annotations, astn):
    """
    Copy the given tree, renaming variables according to the given annotations.
    """
    return RenameVariablesInTree(
        {k: f"{sym}_{id}" for k, (sym, id) in annotations.items()}
    ).visit(astn)


def render_phi_map(phi_map):
    """
    Render the phi map as a mapping from variable to its origin.

    Only phi nodes are rendered.
    """
    return {
        f"{sym}_{id}": "phi(" + ", ".join(f"{sym}_{id}" for sym, id in v.parents) + ")"
        for (sym, id), v in phi_map.items()
        if isinstance(v, Phi)
    }
