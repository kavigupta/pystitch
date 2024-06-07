import neurosym as ns

from imperative_stitch.utils.types import SEPARATOR

from .abstraction_handler import AbstractionHandlerPuller


def def_use_mask(tree_dist, dsl, dfa, abstrs):
    # pylint: disable=cyclic-import
    from .canonicalize_de_bruijn import DBVarHandlerPuller, DBVarSymbolPredicate

    assert isinstance(abstrs, (list, tuple))
    config = ns.python_def_use_mask.DefUseMaskConfiguration(
        dfa,
        {
            "fn_": AbstractionHandlerPuller({x.name: x for x in abstrs}),
            "dbvar" + SEPARATOR: DBVarHandlerPuller(),
        },
    )
    return ns.python_def_use_mask.DefUseChainPreorderMask(
        tree_dist, dsl, config, special_case_predicate_fns=[DBVarSymbolPredicate]
    )
