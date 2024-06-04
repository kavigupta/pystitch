import neurosym as ns


def python_node_ordering_with_abstractions(abstrs):
    result = ns.python_def_use_mask.python_ordering_dictionary()
    for i, abstr in enumerate(abstrs):
        ann_name = abstr.name + "~" + ns.python_ast_tools.clean_type(abstr.dfa_root)
        result[ann_name] = abstr.arguments_traversal_order(
            result, previous_abstractions=abstrs[:i]
        )
    return result


class PythonWithAbstractionsNodeOrdering(ns.DictionaryNodeOrdering):
    """
    Orders the subnodes of a node according to a dictionary.
    """

    def __init__(self, dist, abstrs):
        super().__init__(
            dist,
            python_node_ordering_with_abstractions(abstrs),
            tolerate_missing=True,
        )
