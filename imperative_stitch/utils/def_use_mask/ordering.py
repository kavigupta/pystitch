import ast

from imperative_stitch.parser.parse_python import fields_for_node


def field_order(node, fields):
    node = node.split("~")[0]
    node = getattr(ast, node)
    node_fields = fields_for_node(node)
    assert set(fields) == set(node_fields)
    return [node_fields.index(f) for f in fields]


def python_node_dictionary():
    fields = [
        ("ListComp~E", ["generators", "elt"]),
        ("GeneratorExp~E", ["generators", "elt"]),
        ("SetComp~E", ["generators", "elt"]),
        ("DictComp~E", ["generators", "key", "value"]),
    ]

    result = {}
    for node, fields in fields:
        result[node] = field_order(node, fields)
    return result


def python_node_ordering_with_abstractions(abstrs):
    result = python_node_dictionary()
    for abstr in abstrs:
        result[abstr.name + "~" + abstr.dfa_root] = abstr.arguments_traversal_order(
            result
        )
    return result
