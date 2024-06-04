from imperative_stitch.utils.def_use_mask.mask import (
    DefUseChainPreorderMask,
    DefUseMaskConfiguration,
)
from imperative_stitch.utils.types import SEPARATOR
from .abstraction_handler import AbstractionHandlerPuller


def def_use_mask(tree_dist, dsl, dfa, abstrs):
    # pylint: disable=cyclic-import
    from .canonicalize_de_bruijn import DBVarHandlerPuller, DBVarSymbolPredicate
    assert isinstance(abstrs, (list, tuple))
    config = DefUseMaskConfiguration(
        dfa,
        {
            "fn_": AbstractionHandlerPuller({x.name: x for x in abstrs}),
            "dbvar" + SEPARATOR: DBVarHandlerPuller(),
        },
    )
    return DefUseChainPreorderMask(
        tree_dist, dsl, config, special_case_predicate_fns=[DBVarSymbolPredicate]
    )
