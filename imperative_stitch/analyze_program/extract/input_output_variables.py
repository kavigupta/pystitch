import ast
from collections import defaultdict
from dataclasses import dataclass, field

import ast_scope.scope

from imperative_stitch.analyze_program.extract.errors import (
    ClosedVariablePassedDirectly,
    ClosureOverVariableModifiedInExtractedCode,
    ModifiesVariableClosedOverInNonExtractedCode,
    NonInitializedInputsOrOutputs,
    NotApplicable,
)
from imperative_stitch.analyze_program.ssa.annotator import run_ssa
from imperative_stitch.analyze_program.ssa.ivm import (
    DefinedIn,
    Gamma,
    Origin,
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

    def raise_if_needed(self):
        if self.errors:
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

    @property
    def output_vars_ssa(self):
        return sorted(self._output_vars_ssa)


def compute_variables(
    site, scope_info, pfcfg, error_on_closed=False, guarantee_outputs_of=()
):
    """
    Compute a Variables object for a site. Ignores metavariables.

    Args:
        - site: the extraction site
        - scope_info: a mapping from nodes to scopes
        - pfcfg: the program flow control graph
        - error_on_closed: whether to error if a closed variable is passed directly
        - guarantee_outputs_of: a list of variables that must be outputted, with SSA ids

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
        output_variables = compute_output_variables(site, ssa_to_origin, node_to_ssa)
    output_variables += guarantee_outputs_of
    output_symbols = sorted({x for x, _ in output_variables})
    output_variable_at_exit = {
        end[pre_exit][sym] for pre_exit in pre_exits for sym in output_symbols
    }

    input_variables = compute_input_variables(
        site, ssa_to_origin, node_to_ssa, output_variable_at_exit
    )
    # renormalize the input variables to be the ones that are actually passed in
    # in case the ones used are the result of a phi node
    input_variables = sorted({start[entry][x] for x, _ in input_variables})

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
                ultimate_origins,
                ultimate_origins[closed_ssa_id],
                lambda x: x not in extracted_nodes,
            )
            for closed_ssa_id in ssa_to_origin[ssa_id].closed
        )
    )

    closed_in_parent_variables = sorted(
        ssa_id
        for node in set(node_to_ssa) - set(site.all_nodes)
        for ssa_id in node_to_ssa.get(node, ())
        if isinstance(ssa_to_origin[ssa_id], Gamma)
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
        ultimate_origins,
        [
            origin
            for ssa_id in closed_variables
            for closed_ssa_id in ssa_to_origin[ssa_id].closed
            for origin in ultimate_origins[closed_ssa_id]
        ],
        lambda x: x in extracted_nodes,
    ):
        errors.append(ClosureOverVariableModifiedInExtractedCode)

    for ssa_id in closed_in_parent_variables:
        if traces_an_origin_to_node_set(
            ultimate_origins,
            ultimate_origins[ssa_id],
            lambda x: x in extracted_nodes,
            include_gamma=True,
        ):
            errors.append(ModifiesVariableClosedOverInNonExtractedCode)

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


def is_origin_defined_in_node_set(
    node_to_origin, origin, node_set, include_gamma=False
):
    """
    Is the origin of a variable defined in a given node set?

    Uses the special node set "<<function def>>" to represent the set of nodes that
    define a variable in the function definition (arguments)

    Args:
        - node_to_origin: a mapping from nodes to origins
        - origin: the origin of a variable
        - node_set: a set of nodes, represented as a function from nodes to bool
        - include_gamma: whether to include the origins of closed variables

    Returns
        True if the origin of the variable is a DefinedIn node and the site of the
        DefinedIn node is in the node set. Returns False otherwise.
    """
    assert isinstance(origin, Origin)
    if isinstance(origin, DefinedIn):
        return node_set(origin.site)
    elif isinstance(origin, Phi):
        return node_set(origin.node)
    elif isinstance(origin, Gamma):
        return include_gamma and any(
            is_origin_defined_in_node_set(node_to_origin, origin, node_set)
            for closed_var in origin.closed
            for origin in node_to_origin[closed_var]
        )  # do not include anywhere
    else:
        return node_set("<<function def>>")


def traces_an_origin_to_node_set(
    node_to_origin, origins, node_set, include_gamma=False
):
    """
    Traces the origins of a variable to see if any of them are defined in a given node set

    Args:
        - node_to_origin: a mapping from nodes to origins
        - origins: the origins of a variable
        - node_set: a set of nodes, represented as a function from nodes to bool

    Returns:
        True if any of the origins of the variable are defined in the node set. Returns
        False otherwise.
    """
    return any(
        is_origin_defined_in_node_set(
            node_to_origin, origin, node_set, include_gamma=include_gamma
        )
        for origin in origins
    )


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


def is_output_journey(journey):
    """
    Is the journey an output journey?

    That is, does it leave the set, by moving from inside the set (True) to outside the set (False)?
    """
    return (True, False) in zip(journey, journey[1:])


def is_input_journey(journey):
    """
    Is the journey an input journey?

    That is, does it enter the set, by moving from outside the set (False) to inside the set (True)?
    """
    return (False, True) in zip(journey, journey[1:])


def origin_paths(ssa_id, id_to_origin, handle_gamma=False, suffix=()):
    """
    Get the paths describing the origin of a variable

    Args:
        - ssa_id: the SSA id of the variable
        - id_to_origin: a mapping from SSA ids to origins
        - handle_gamma: whether to handle gamma nodes
        - suffix: the suffix of the path (for recursion, added to the end of the path)

    Yields:
        A path describing the origin of the variable, as a tuple of AST nodes
    """
    origin = id_to_origin[ssa_id]
    if isinstance(origin, DefinedIn):
        yield (origin.site.instruction.node, *suffix)
    elif isinstance(origin, Phi):
        for x in origin.parents:
            if origin.node in suffix:
                yield (origin.node, *suffix)
            else:
                yield from origin_paths(x, id_to_origin, suffix=(*suffix, origin.node))
    elif isinstance(origin, Gamma):
        if handle_gamma:
            for x in origin.closed:
                yield from origin_paths(x, id_to_origin, suffix=suffix)

    else:
        yield ("<<function def>>",)


def get_variable_journeys(ssa_to_origin, node_to_ssa, *, node_predicate, handle_gamma):
    """
    Gets the journeys for each SSA id.

    Args:
        - ssa_to_origin: a mapping from SSA ids to origins
        - node_to_ssa: a mapping from nodes to SSA ids
        - node_predicate: a function that returns whether a node is in the set
        - handle_gamma: whether to handle gamma nodes

    Returns:
        A mapping from SSA ids to journeys (as a list of tuples of booleans)
    """
    node_journeys = defaultdict(list)
    for node in node_to_ssa:
        for ssa_id in node_to_ssa[node]:
            node_journeys[ssa_id] += [
                tuple(node_predicate(x) for x in (*path, node))
                for path in origin_paths(
                    ssa_id, ssa_to_origin, handle_gamma=handle_gamma
                )
            ]
    return node_journeys


def compute_output_variables(site, ssa_to_origin, node_to_ssa):
    """
    Like compute_input_variables, but for output variables.

    Args:
        - site: the extraction site
        - ssa_to_origin: a mapping from SSA ids to origins
        - node_to_ssa: a mapping from nodes to SSA ids

    Returns:
        A list of SSA ids representing the variables that need to be outputted
    """
    node_journeys = get_variable_journeys(
        ssa_to_origin,
        node_to_ssa,
        node_predicate=lambda x: x in site.all_nodes,
        handle_gamma=True,
    )

    result = []

    for ssa_id in node_journeys:
        if any(is_output_journey(j) for j in node_journeys[ssa_id]):
            result.append(ssa_id)

    return sorted(result)


def compute_input_variables(site, ssa_to_origin, node_to_ssa, out):
    """
    Computes the input variables for a site.

    Args:
        - site: the extraction site
        - ssa_to_origin: a mapping from SSA ids to origins
        - node_to_ssa: a mapping from nodes to SSA ids
        - out: the SSA ids representing the variables that need to be outputted
    """
    node_journeys = get_variable_journeys(
        ssa_to_origin,
        node_to_ssa,
        node_predicate=lambda x: x in site.all_nodes,
        handle_gamma=False,
    )
    for x in out:
        if x in node_journeys:
            node_journeys[x] += [
                (*path[:-1], True, path[-1]) for path in node_journeys[x]
            ]
        else:
            node_journeys[x] = [(False, True, False)]

    result = []

    for ssa_id in node_journeys:
        if any(is_input_journey(j) for j in node_journeys[ssa_id]):
            result.append(ssa_id)

    return sorted(result)
