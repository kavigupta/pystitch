import ast
from dataclasses import dataclass, field

import ast_scope.scope

from imperative_stitch.analyze_program.extract.errors import (
    ClosedVariablePassedDirectly,
    ClosureOverVariableModifiedInExtractedCode,
    NonInitializedInputsOrOutputs,
    NotApplicable,
)
from imperative_stitch.analyze_program.ssa.annotator import run_ssa
from imperative_stitch.analyze_program.ssa.ivm import (
    DefinedIn,
    Gamma,
    Phi,
    compute_ultimate_origins,
)


@dataclass
class Variables:
    """
    Represents the variables that interact with a site at its boundaries.
        Each is a list of (variable name, ssa id) pairs.

    Specifically,
        - input_vars: variables that are accessed directly in the site but are not defined in the site
            e.g., if the site is `x = y + z`, then `y` and `z` are input variables
        - closed_vars: variables that are closed over in the site but are not defined in the site
            e.g., if the site is `z = lambda x: x + y`, then `y` is a closed variable
        - output_vars: variables that are accessed outside the site but are defined in the site
    """

    _input_vars_ssa: list[(str, int)]
    _closed_vars_ssa: list[(str, int)]
    _output_vars_ssa: list[(str, int)]
    _parent_vars_no_ssa: list[str] = field(default_factory=lambda: [])
    errors: list[NotApplicable] = field(default_factory=lambda: [])

    def raise_if_needed(self, undos):
        if self.errors:
            for undo in undos[::-1]:
                undo()
            raise self.errors[0]

    def is_input(self, node, node_to_ssa):
        if node in node_to_ssa:
            [ssa] = node_to_ssa[node]
            return self.is_ssa_id_input(ssa)
        return node.id in self._parent_vars_no_ssa

    def is_ssa_id_input(self, ssa_id):
        assert (
            isinstance(ssa_id, tuple)
            and len(ssa_id) == 2
            and isinstance(ssa_id[0], str)
            and isinstance(ssa_id[1], int)
        )
        return ssa_id in self._input_vars_ssa

    @property
    def input_vars_without_ssa(self):
        return sorted(
            {x for x, _ in self._input_vars_ssa} | set(self._parent_vars_no_ssa)
        )

    @property
    def closed_vars_without_ssa(self):
        return sorted({x for x, _ in self._closed_vars_ssa})

    @property
    def output_vars_without_ssa(self):
        return sorted({x for x, _ in self._output_vars_ssa})


def compute_variables(site, scope_info, pfcfg, error_on_closed=False):
    """
    Compute a Variables object for a site. Ignores metavariables.

    Args:
        - site: the extraction site
        - scope_info: a mapping from nodes to scopes
        - pfcfg: the program flow control graph

    Returns:
        A Variables object
    """
    start, end, ssa_to_origin, node_to_ssa = run_ssa(scope_info, pfcfg)
    extracted_nodes = {x for x in start if x.instruction.node in site.all_nodes}
    entry, exit, pre_exits = pfcfg.extraction_entry_exit(extracted_nodes)
    ultimate_origins = compute_ultimate_origins(ssa_to_origin)

    if exit is None or exit == "<return>":
        output_variables = []
    else:
        output_variables = compute_output_variables(
            pfcfg, site, node_to_ssa, ultimate_origins, extracted_nodes
        )
    output_symbols = sorted({x for x, _ in output_variables})
    output_variable_at_exit = {
        end[pre_exit][sym] for pre_exit in pre_exits for sym in output_symbols
    }

    input_variables = compute_input_variables(
        site,
        node_to_ssa,
        ultimate_origins,
        extracted_nodes,
        output_variables=output_variable_at_exit,
    )
    parent_variables = variables_from_parent(
        site, node_to_ssa, scope_info, pfcfg.function_astn
    )

    extracted_variables = [
        ssa_id for node in site.all_nodes for ssa_id in node_to_ssa.get(node, ())
    ]

    closed_variables = sorted(
        ssa_id
        for ssa_id in extracted_variables
        if isinstance(ssa_to_origin[ssa_id], Gamma)
        if any(
            traces_an_origin_to_node_set(
                ultimate_origins[closed_ssa_id], lambda x: x not in extracted_nodes
            )
            for closed_ssa_id in ssa_to_origin[ssa_id].closed
        )
    )
    errors = []
    if entry is not None and not all_initialized(
        start[entry], [x for x, _ in input_variables], ultimate_origins
    ):
        errors.append(NonInitializedInputsOrOutputs)

    for pre_exit in pre_exits:
        if not all_initialized(
            end[pre_exit], [x for x, _ in output_variables], ultimate_origins
        ):
            errors.append(NonInitializedInputsOrOutputs)

    if traces_an_origin_to_node_set(
        [
            origin
            for ssa_id in closed_variables
            for closed_ssa_id in ssa_to_origin[ssa_id].closed
            for origin in ultimate_origins[closed_ssa_id]
        ],
        lambda x: x in extracted_nodes,
    ):
        errors.append(ClosureOverVariableModifiedInExtractedCode)

    if error_on_closed and closed_variables:
        errors.append(ClosedVariablePassedDirectly)

    return Variables(
        input_variables,
        closed_variables,
        output_variables,
        parent_variables,
        errors=errors,
    )


def all_initialized(lookup, vars, ultimate_origins):
    """
    Whether all the variables are initialized in their ultimate origin

    Arguments
    ---------
    lookup: dict[str, (str, int)]
        A mapping from variable to its SSA entry.
    vars: list[str]
        The variables to check.
    ultimate_origins: dict[(str, int), origin]
        A mapping from SSA entry to its ultimate origin.

    Returns
    -------
    bool
        True if all the variables are initialized in their ultimate origin.
    """
    vars = [lookup[v] for v in vars]
    return all(all(x.initialized() for x in ultimate_origins[var]) for var in vars)


def is_origin_defined_in_node_set(origin, node_set):
    """
    Is the origin of a variable defined in a given node set?

    Uses the special node set "<<function def>>" to represent the set of nodes that
    define a variable in the function definition (arguments)

    Args:
        - origin: the origin of a variable
        - node_set: a set of nodes, represented as a function from nodes to bool

    Returns
        True if the origin of the variable is a DefinedIn node and the site of the
        DefinedIn node is in the node set. Returns False otherwise.
    """
    if isinstance(origin, DefinedIn):
        return node_set(origin.site)
    elif isinstance(origin, Phi):
        return node_set(origin.node)
    elif isinstance(origin, Gamma):
        return False  # do not include anywhere
    else:
        return node_set("<<function def>>")


def traces_an_origin_to_node_set(origins, node_set):
    """
    Traces the origins of a variable to see if any of them are defined in a given node set

    Args:
        - origins: the origins of a variable
        - node_set: a set of nodes, represented as a function from nodes to bool

    Returns:
        True if any of the origins of the variable are defined in the node set. Returns
        False otherwise.
    """
    return any(is_origin_defined_in_node_set(origin, node_set) for origin in origins)


def variables_in_nodes(nodes, annotations):
    """
    Get all the variables that are defined in a set of nodes.

    Args:
        - nodes: a set of nodes
        - annotations: a mapping from a node to the set of variables defined in the node

    Returns:
        A set of variables that are defined in the given nodes.
    """
    return {alias for x in nodes if x in annotations for alias in annotations[x]}


def variables_from_parent(site, annotations, scope_info, function_astn):
    """
    Variables that are defined in the parent function of the extraction site.

    Args:
        - site: the extraction site
        - annotations: a mapping from a node to the set of variables defined in the node
        - scope_info: a mapping from nodes to scopes

    Returns:
        A list of variables that are defined in the parent function of the extraction site.
    """
    function_nodes = set(ast.walk(function_astn))
    result = set()
    for node in site.all_nodes:
        if node in annotations:
            continue
        if node not in scope_info:
            continue
        scope = scope_info[node]
        if not isinstance(scope, ast_scope.scope.FunctionScope):
            continue
        if scope.function_node in function_nodes:
            continue
        result.add(node.id)

    return sorted(result)


def compute_input_variables(
    site, annotations, ultimate_origins, extracted_nodes, *, output_variables
):
    """
    Compute the input variables of an extraction site.

    Args:
        - site: the extraction site
        - annotations: a mapping from a node to the set of variables defined in the node
        - ultimate_origins: a mapping from a variable to the ultimate origins of the variable
        - extracted_nodes: the set of nodes in the extraction site
        - output_variables: the output variables of the extraction site

    Returns:
        A list of input variables, sorted by name.
    """
    variables_in = variables_in_nodes(site.all_nodes, annotations) | set(
        output_variables
    )
    variables_in = sorted(
        [
            x
            for x in variables_in
            if traces_an_origin_to_node_set(
                ultimate_origins[x], lambda x: x not in extracted_nodes
            )
        ]
    )
    return variables_in


def compute_output_variables(
    pfcfg, site, annotations, ultimate_origins, extracted_nodes
):
    """
    Like compute_input_variables, but for output variables.
    """
    variables_out = variables_in_nodes(
        set(pfcfg.astn_order) - site.all_nodes, annotations
    )
    return sorted(
        {
            x
            for x in variables_out
            if traces_an_origin_to_node_set(
                ultimate_origins[x], lambda x: x in extracted_nodes
            )
        }
    )
