from typing import Tuple

from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.compress.manipulate_abstraction import (
    abstraction_calls_to_bodies,
)


def add_abstractions(subset, dfa, *abstrs: Tuple[Abstraction, ...]):
    """
    Add the bodies of the abstractions to the subset.
    """
    abstrs_dict = {a.name: a for a in abstrs}
    return subset.add_programs(
        dfa,
        *[abstraction_calls_to_bodies(a.body, abstrs_dict) for a in abstrs],
        root=[a.dfa_root for a in abstrs],
    )
