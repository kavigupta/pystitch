import ast

import neurosym as ns


def python_node_dictionary():
    result = {}
    assert ast.ListComp._fields == ("elt", "generators")
    result["ListComp~E"] = [1, 0]  # reversed
    assert ast.GeneratorExp._fields == ("elt", "generators")
    result["GeneratorExp~E"] = [1, 0]  # reversed
    assert ast.SetComp._fields == ("elt", "generators")
    result["SetComp~E"] = [1, 0]  # reversed
    assert ast.DictComp._fields == ("key", "value", "generators")
    result["DictComp~E"] = [2, 0, 1]  # put generators first
    return result


def python_node_ordering_with_abstractions(abstrs):
    result = python_node_dictionary()
    for i, abstr in enumerate(abstrs):
        result[abstr.name + "~" + abstr.dfa_root] = abstr.arguments_traversal_order(
            result, previous_abstractions=abstrs[:i]
        )
    print("orderings", result)
    return result


class PythonNodeOrdering(ns.DictionaryNodeOrdering):
    """
    Orders the subnodes of a node according to a dictionary.
    """

    def __init__(self, dist, abstrs):
        super().__init__(
            dist,
            python_node_ordering_with_abstractions(abstrs),
            tolerate_missing=True,
        )
