import neurosym as ns

from imperative_stitch.parser.parse_python import fields_for_node
from imperative_stitch.utils.export_as_dsl import clean_type


def field_order(node, fields):
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
    for i, abstr in enumerate(abstrs):
        ann_name = abstr.name + "~" + clean_type(abstr.dfa_root)
        result[ann_name] = abstr.arguments_traversal_order(
            result, previous_abstractions=abstrs[:i]
        )
    return result


class PythonNodeOrdering(ns.DictionaryNodeOrdering):
    """
    Orders the subnodes of a node according to a dictionary.
    """

    def __init__(self, dist):
        super().__init__(
            dist,
            python_node_ordering_with_abstractions([]),
            tolerate_missing=True,
        )
