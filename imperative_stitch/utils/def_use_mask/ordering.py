import ast


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
    for abstr in abstrs:
        result[abstr.name + "~" + abstr.dfa_root] = abstr.arguments_traversal_order(
            result
        )
    return result
