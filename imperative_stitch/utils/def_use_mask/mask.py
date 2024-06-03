import copy
from dataclasses import dataclass
from typing import Dict, List

import neurosym as ns

from imperative_stitch.utils.def_use_mask.abstraction_handler import (
    AbstractionHandlerPuller,
)
from imperative_stitch.utils.def_use_mask.extra_var import (
    ExtraVar,
    canonicalized_python_name_leaf_regex,
)
from imperative_stitch.utils.def_use_mask.handler import (
    DefaultHandler,
    HandlerPuller,
    default_handler,
)
from imperative_stitch.utils.def_use_mask.names import NAME_REGEX
from imperative_stitch.utils.def_use_mask.ordering import PythonNodeOrdering
from imperative_stitch.utils.def_use_mask.special_case_symbol_predicate import (
    NameEPredicate,
)
from imperative_stitch.utils.types import SEPARATOR


@dataclass
class DefUseMaskConfiguration:
    dfa: Dict
    node_hooks: Dict[str, HandlerPuller]

    def get_hook(self, symbol):
        prefixes = [x for x in self.node_hooks if symbol.startswith(x)]
        if not prefixes:
            return None
        assert len(prefixes) == 1, f"Multiple hooks found for {symbol}: {prefixes}"
        return self.node_hooks[prefixes[0]]

    def pull_handler(
        self,
        position: int,
        symbol: str,
        mask: "DefUseChainPreorderMask",
        defined_production_idxs: List[int],
    ):
        hook = self.get_hook(symbol)
        if hook is None:
            return None
        return hook.pull_handler(
            position,
            symbol,
            mask,
            defined_production_idxs,
            self,
            handler_fn=default_handler,
        )


class DefUseChainPreorderMask(ns.PreorderMask):
    """
    Preorder mask that filters out symbols that are not defined at a given position.

    The idea is to have a stack of Handler objects, one for each node in the syntax tree.

    Args:
        tree_dist: The tree distribution that the mask is applied to.
        dsl: The domain-specific language that the mask is applied to.
        dfa: The DFA of the DSL
        abstrs: The abstractions of the DSL
    """

    def __init__(self, tree_dist, dsl, dfa, abstrs):
        # pylint: disable=cyclic-import
        from .canonicalize_de_bruijn import (
            DBVarHandlerPuller,
            DBVarSymbolPredicate,
            compute_de_bruijn_limit,
        )

        super().__init__(tree_dist)
        assert isinstance(tree_dist.ordering, PythonNodeOrdering)
        assert isinstance(abstrs, (list, tuple))
        self.dsl = dsl
        self.idx_to_name = []
        for x, _ in self.tree_dist.symbols:
            mat = NAME_REGEX.match(x)
            self.idx_to_name.append(mat.group("name") if mat else None)

        self.special_case_predicates = [
            NameEPredicate(self.tree_dist),
            DBVarSymbolPredicate(self.tree_dist),
        ]

        self.handlers = []
        self.config = DefUseMaskConfiguration(
            dfa,
            {
                "fn_": AbstractionHandlerPuller({x.name: x for x in abstrs}),
                "dbvar" + SEPARATOR: DBVarHandlerPuller(),
            },
        )
        self.max_explicit_dbvar_index = compute_de_bruijn_limit(tree_dist)

    def currently_defined_indices(self):
        """
        Return the indices of the symbols that are currently defined.
        """
        return self.handlers[-1].currently_defined_indices()

    def compute_mask(self, position: int, symbols: List[int]) -> List[bool]:
        """
        Compute the mask for the given position and symbols. If the last handler is
            defining, then all symbols are valid. Otherwise, only the symbols that
            match the handler's names are valid.
        """
        handler = self.handlers[-1]
        return handler.compute_mask(
            position, symbols, self.idx_to_name, self.special_case_predicates
        )

    def on_entry(self, position: int, symbol: int):
        """
        Updates the stack of handlers when entering a node.
        """
        # pylint: disable=cyclic-import
        if not self.handlers:
            assert position == symbol == 0
            self.handlers.append(DefaultHandler(self, [], self.config))
        else:
            self.handlers.append(self.handlers[-1].on_child_enter(position, symbol))

    def on_exit(self, position: int, symbol: int):
        """
        Updates the stack of handlers when exiting a node.
        """
        popped = self.handlers.pop()
        if not self.handlers:
            assert position == symbol == 0
            return
        self.handlers[-1].on_child_exit(position, symbol, popped)

    def with_handler(self, handler_fn):
        mask_copy = copy.copy(self)
        handler = handler_fn(mask_copy)
        mask_copy.handlers = [handler]
        return mask_copy

    def id_to_name_and_arity(self, symbol_id):
        """
        Convert the symbol ID to a string of the symbol name, and the arity of the symbol.
        """

        if isinstance(symbol_id, ExtraVar):
            return symbol_id.leaf_name(), 0
        return self.tree_dist.symbols[symbol_id]

    def id_to_name(self, symbol_id):
        """
        Convert the symbol ID to a string.
        """
        return self.id_to_name_and_arity(symbol_id)[0]

    def name_to_id(self, name: str):
        """
        Convert the string to a symbol ID.
        """
        if canonicalized_python_name_leaf_regex.match(name):
            assert name not in self.tree_dist.symbol_to_index
            evar = ExtraVar.from_name(name)
            if evar is not None:
                return evar
        return self.tree_dist.symbol_to_index[name]
