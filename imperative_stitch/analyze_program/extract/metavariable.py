import ast
from dataclasses import dataclass

from ast_scope.scope import GlobalScope, ErrorScope, FunctionScope, ClassScope
from imperative_stitch.analyze_program.ssa.ivm import Gamma

from imperative_stitch.utils.ast_utils import ReplaceNodes, ast_nodes_in_order


def variables_needed_to_extract(scope_info, extract_node, node_to_ssa, variables):
    """
    Compute the variables needed to be passed in to extract the given node.
        These are the variables that are used in the extract_node, but are not
        available at the call site. This includes variables that are scoped
        to a function nested in the extracted function as well as variables
        (re)defined

    Args:
        scope_info (dict): A dictionary mapping AST nodes to their scope.
        extract_node (ast.AST): The node to extract.
        node_to_ssa (dict): A dictionary mapping AST nodes to their ssas.
        variables (Variables): The input, closed, and output variables of the site

    Returns:
        list[str]: A list of variable names that are needed to extract the given node.
    """
    node_list = ast_nodes_in_order(extract_node)
    nodes = set(node_list)
    name_to_scope = {}
    for node in node_list:
        if node not in scope_info:
            continue
        if isinstance(scope_info[node], (GlobalScope, ErrorScope)):
            continue
        assert not isinstance(
            scope_info[node], ClassScope
        ), "cannot be a class scope, should have been excluded before now"
        if isinstance(scope_info[node], FunctionScope):
            if scope_info[node].function_node in nodes:
                continue
        if variables.is_input(node, node_to_ssa):
            continue

        if node.id in name_to_scope:
            assert name_to_scope[node.id] == scope_info[node]
        else:
            name_to_scope[node.id] = scope_info[node]
    return list(name_to_scope)


def extract_as_function(
    scope_info,
    metavariable_node,
    node_to_ssa,
    metavariable_name,
    variables,
):
    """
    Extract the given metavariable node as a function.

    Args:
        scope_info (dict): A dictionary mapping AST nodes to their scope.
        metavariable_node (ast.AST): The metavariable node to extract.
        node_to_ssa (dict): A dictionary mapping AST nodes to their ssas.
        metavariable_name (str): The name of the metavariable.
        variables (Variables): The input, closed, and output variables of the site

    Returns:
        ast.Lambda: The parameter to be passed in.
        ast.Call: The call to the metavariable that replaces the metavariable_node.
    """
    variables = variables_needed_to_extract(
        scope_info, metavariable_node, node_to_ssa, variables
    )
    args = ast.arguments(
        args=[ast.arg(v) for v in variables],
        posonlyargs=[],
        vararg=None,
        kwonlyargs=[],
        kw_defaults=[],
        kwarg=None,
        defaults=[],
    )
    parameter = ast.Lambda(args=args, body=metavariable_node)
    call = ast.Call(
        func=ast.Name(id=metavariable_name, ctx=ast.Load()),
        args=[ast.Name(id=x, ctx=ast.Load()) for x in variables],
        keywords=[],
    )
    if isinstance(metavariable_node, (ast.Yield, ast.YieldFrom)):
        call = ast.YieldFrom(call)
    return parameter, call


def extract_metavariables(scope_info, site, node_to_ssa, variables):
    """
    Extract all metavariables in the given site.

    Args:
        scope_info (dict): A dictionary mapping AST nodes to their scope.
        site (ExtractionSite): The site to extract metavariables from.
        node_to_ssa (dict): A dictionary mapping AST nodes to their ssas.
        variables (Variables): The input, closed, and output variables of the site

    Returns:
        MetaVariables: The extracted metavariables.
    """
    texts = {}
    parameters = {}
    replacements = []
    for metavariable_name, metavariable_node in site.metavariables:
        assert isinstance(metavariable_node, ast.AST)
        if metavariable_name in texts:
            assert texts[metavariable_name] == ast.unparse(metavariable_node)

        parameter, call = extract_as_function(
            scope_info,
            metavariable_node,
            node_to_ssa,
            metavariable_name,
            variables,
        )
        texts[metavariable_name] = ast.unparse(metavariable_node)
        parameters[metavariable_name] = parameter
        replacements.append(
            (metavariable_name, MetaVariableReplacement(metavariable_node, call))
        )
    return MetaVariables(parameters, replacements)


@dataclass
class MetaVariableReplacement:
    """
    Represents a metavariable.

    Fields:
        node (ast.AST): The metavariable node.
        call (ast.Call): The call to the metavariable that replaces the metavariable node, if the metavariable is extracted.
    """

    node: ast.AST
    call: ast.Call


class MetaVariables:
    """
    Represents a set of metavariables.

    Fields:
        metavariables (list[(str, (ast.AST, ast.Lambda, ast.Call))]): A list of metavariables.
    """

    def __init__(self, parameters, replacements):
        self._parameters = parameters
        self._replacements = replacements

    def act(self, node):
        forward = {meta.node: meta.call for _, meta in self._replacements}
        backward = {meta.call: meta.node for _, meta in self._replacements}
        ReplaceNodes(forward).visit(node)
        return lambda: ReplaceNodes(backward).visit(node)

    @property
    def names(self):
        return sorted(self._parameters)

    @property
    def parameters(self):
        return [self._parameters[name] for name in self.names]

    def parameter_for_name(self, name):
        return self._parameters[name]

    def replacements_for_name(self, name):
        return [meta for meta_name, meta in self._replacements if meta_name == name]

    @property
    def all_calls(self):
        return [meta.call for _, meta in self._replacements]
