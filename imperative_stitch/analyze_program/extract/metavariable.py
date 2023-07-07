import ast

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
        if node in node_to_ssa:
            [ssa] = node_to_ssa[node]
            if variables.is_input(ssa):
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
    result = {}
    for metavariable_name, metavariable_node in site.metavariables.items():
        parameter, call = extract_as_function(
            scope_info,
            metavariable_node,
            node_to_ssa,
            metavariable_name,
            variables,
        )
        result[metavariable_name] = metavariable_node, parameter, call
    return MetaVariables(result)


class MetaVariables:
    """
    Represents a set of metavariables.
    """

    def __init__(self, metavariables):
        self.metavariables = metavariables

    def act(self, node):
        forward = {node: call for node, _, call in self.metavariables.values()}
        backward = {call: node for node, _, call in self.metavariables.values()}
        ReplaceNodes(forward).visit(node)
        return lambda: ReplaceNodes(backward).visit(node)

    @property
    def names(self):
        return list(self.metavariables)

    @property
    def parameters(self):
        return [parameter for _, parameter, _ in self.metavariables.values()]
