from imperative_stitch.analyze_program.ssa.ivm import DefinedIn, Gamma, Phi


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


def compute_input_variables(
    site, annotations, ultimate_origins, extracted_nodes, keep_ssa=False
):
    """
    Compute the input variables of an extraction site.

    Args:
        - site: the extraction site
        - annotations: a mapping from a node to the set of variables defined in the node
        - ultimate_origins: a mapping from a variable to the ultimate origins of the variable
        - extracted_nodes: the set of nodes in the extraction site

    Returns:
        A list of input variables, sorted by name.
    """
    variables_in = variables_in_nodes(site.all_nodes, annotations)
    variables_in = sorted(
        [
            x
            for x in variables_in
            if traces_an_origin_to_node_set(
                ultimate_origins[x], lambda x: x not in extracted_nodes
            )
        ]
    )
    if keep_ssa:
        return variables_in
    var_set = sorted(set(var for var, _ in variables_in))
    return var_set


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
            x[0]
            for x in variables_out
            if traces_an_origin_to_node_set(
                ultimate_origins[x], lambda x: x in extracted_nodes
            )
        }
    )
