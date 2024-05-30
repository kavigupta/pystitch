import json

import neurosym as ns
from frozendict import frozendict

from imperative_stitch.utils.types import non_sequence_prefixes


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


def add_disambiguating_type_tags(dfa, prog, start_state):
    return ns.add_disambiguating_type_tags(
        dfa, prog, start_state, non_sequence_prefixes
    )


if __name__ == "__main__":
    print(json.dumps(export_dfa(), indent=2))
