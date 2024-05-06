import copy
from dataclasses import dataclass
from typing import Dict, List

import neurosym as ns

from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.utils.def_use_mask.extra_var import ExtraVar
from imperative_stitch.utils.def_use_mask.handler import DefaultHandler
from imperative_stitch.utils.def_use_mask.names import GLOBAL_REGEX, NAME_REGEX
from imperative_stitch.utils.def_use_mask.ordering import PythonNodeOrdering


@dataclass
class DefUseMaskConfiguration:
    dfa: Dict
    abstractions: Dict[str, Abstraction]


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
        from .canonicalize_de_bruijn import compute_de_bruijn_limit

        super().__init__(tree_dist)
        assert isinstance(tree_dist.ordering, PythonNodeOrdering)
        assert isinstance(abstrs, (list, tuple))
        self.dsl = dsl
        self.has_global_available = any(
            GLOBAL_REGEX.match(x) for x, _ in self.tree_dist.symbols
        )
        self.handlers = []
        self.config = DefUseMaskConfiguration(dfa, {x.name: x for x in abstrs})
        self.de_bruijn_limit = compute_de_bruijn_limit(tree_dist)
        self.de_bruijn_mask_handler = None

    def _matches(self, names, symbol_id):
        """
        Whether or not the symbol matches the names.
        """
        # pylint: disable=cyclic-import
        from .canonicalize_de_bruijn import is_dbvar_wrapper_symbol

        symbol = self.id_to_name(symbol_id)
        if symbol == "Name~E":
            return self.has_global_available or len(names) > 0
        if is_dbvar_wrapper_symbol(symbol):
            assert self.de_bruijn_mask_handler is None
            return len(names) > 0
        mat = NAME_REGEX.match(symbol)
        if not mat:
            return True
        return mat.group("name") in names

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
        is_defn = handler.is_defining(position)
        if self.de_bruijn_mask_handler is not None:
            return self.de_bruijn_mask_handler.compute_mask(symbols, is_defn)
        if is_defn:
            return [True] * len(symbols)
        names = handler.currently_defined_names()
        return [self._matches(names, symbol) for symbol in symbols]

    def on_entry(self, position: int, symbol: int):
        """
        Updates the stack of handlers when entering a node.
        """
        # pylint: disable=cyclic-import
        from .canonicalize_de_bruijn import DeBruijnMaskHandler, is_dbvar_wrapper_symbol

        if is_dbvar_wrapper_symbol(self.id_to_name(symbol)):
            assert self.de_bruijn_mask_handler is None
            self.de_bruijn_mask_handler = DeBruijnMaskHandler(
                self.tree_dist,
                self.de_bruijn_limit,
                len(self.currently_defined_indices()),
            )
            return
        if self.de_bruijn_mask_handler is not None:
            self.de_bruijn_mask_handler.on_entry(symbol)
            return
        if not self.handlers:
            assert position == symbol == 0
            self.handlers.append(DefaultHandler(self, [], self.config))
        else:
            self.handlers.append(self.handlers[-1].on_child_enter(position, symbol))

    def on_exit(self, position: int, symbol: int):
        """
        Updates the stack of handlers when exiting a node.
        """
        if self.de_bruijn_mask_handler is not None:
            symbol = self.de_bruijn_mask_handler.on_exit(symbol)
            if symbol is None:
                return
            self.de_bruijn_mask_handler = None
            self.on_entry(position, symbol)
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
        from .canonicalize_de_bruijn import canonicalized_python_name_as_leaf

        if isinstance(symbol_id, ExtraVar):
            return canonicalized_python_name_as_leaf(symbol_id.id, use_type="Name"), 0
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
        from .canonicalize_de_bruijn import canonicalized_python_name_leaf_regex

        mat = canonicalized_python_name_leaf_regex.match(name)
        if name not in self.tree_dist.symbol_to_index and mat:
            return ExtraVar(int(mat.group("var")))

        return self.tree_dist.symbol_to_index[name]
