import copy
import json

import neurosym as ns
from frozendict import frozendict

from imperative_stitch.utils.types import SEPARATOR, clean_type, is_sequence


def export_dfa(*, abstrs=frozendict({})):
    """
    Takes a transition dictionary of the form above and converts
        it to a dict[state, dict[tag, list[state]]].

    """

    if isinstance(abstrs, (list, tuple)):
        abstrs = {x.name: x for x in abstrs}

    assert isinstance(abstrs, (dict, frozendict)), f"expected dict, got {abstrs}"

    result = ns.python_dfa()

    for k, abstr in abstrs.items():
        assert k == abstr.name, (k, abstr.name)
        result[abstr.dfa_root][k] = (
            abstr.dfa_metavars + abstr.dfa_symvars + abstr.dfa_choicevars
        )

    return result


def classify_nodes_in_program(dfa, node, state):
    if not isinstance(node, (ns.SExpression, str)):
        raise ValueError(f"expected SExpression or str, got {node}")
    yield node, state
    if not isinstance(node, ns.SExpression):
        return
    if not node.children:
        # avoid looking up dfa[state][tag] when there are no children; allows sparser dfa
        return
    if state not in dfa:
        raise ValueError(f"state {state} not in dfa")
    if node.symbol not in dfa[state]:
        raise ValueError(f"symbol {node.symbol} not in dfa[{state}]")
    dfa_states = dfa[state][node.symbol]
    for i, child in enumerate(node.children):
        yield from classify_nodes_in_program(
            dfa, child, dfa_states[i % len(dfa_states)]
        )


def add_disambiguating_type_tags(dfa, prog, start_state):
    prog = copy.deepcopy(prog)
    node_id_to_new_symbol = {}
    for node, tag in classify_nodes_in_program(dfa, prog, start_state):
        assert isinstance(node, ns.SExpression), node
        new_symbol = node.symbol + SEPARATOR + clean_type(tag)
        if is_sequence(tag, node.symbol):
            new_symbol += SEPARATOR + str(len(node.children))
        node_id_to_new_symbol[id(node)] = new_symbol
    return prog.replace_symbols_by_id(node_id_to_new_symbol)


if __name__ == "__main__":
    print(json.dumps(export_dfa(), indent=2))
