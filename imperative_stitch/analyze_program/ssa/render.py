from _ast import AST
import ast
import copy

from imperative_stitch.analyze_program.ssa.ivm import Gamma, Phi
from imperative_stitch.utils.non_mutating_node_transformer import (
    NonMutatingNodeTransformer,
)


class RenameVariablesInTree(NonMutatingNodeTransformer):
    def __init__(self, renamed_variables):
        super().__init__()
        self.renamed_variables = renamed_variables

    def visit_Name(self, astn):
        return self.create_new_element(astn, "id")

    def visit_arg(self, astn):
        return self.create_new_element(astn, "arg")

    def visit_FunctionDef(self, astn):
        astn = self.create_new_element(astn, "name")
        astn = super().generic_visit(astn)
        return astn

    def visit_ExceptHandler(self, astn):
        astn = self.create_new_element(astn, "name")
        astn = super().generic_visit(astn)
        return astn

    def create_new_element(self, astn, field_name):
        # generalize the above two
        if astn in self.renamed_variables:
            astn_copy = copy.copy(astn)
            setattr(astn_copy, field_name, self.renamed_variables[astn])
            return astn_copy
        return astn


def rename_to_ssa(annotations, astn):
    """
    Copy the given tree, renaming variables according to the given annotations.
    """
    return RenameVariablesInTree(
        {k: compute_modified_name(name) for k, name in annotations.items()}
    ).visit(astn)


def render_phi_map(phi_map):
    """
    Render the phi map as a mapping from variable to its origin.

    Only phi and gamma nodes are rendered.
    """
    result = {}
    for name, v in phi_map.items():
        if isinstance(v, Phi):
            result[compute_modified_name([name])] = (
                "phi("
                + ", ".join(compute_modified_name([(sym, id)]) for sym, id in v.parents)
                + ")"
            )
        elif isinstance(v, Gamma):
            result[compute_modified_name([name])] = (
                "gamma("
                + ", ".join(compute_modified_name([(sym, id)]) for sym, id in v.closed)
                + ")"
            )
    return result


def compute_modified_name(sym_ids):
    return "_".join(f"{sym}_{id}" for sym, id in sym_ids)
