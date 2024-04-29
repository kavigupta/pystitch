from dataclasses import dataclass
from typing import List

import neurosym as ns

from imperative_stitch.utils.def_use_mask.handler import DefaultHandler
from imperative_stitch.utils.def_use_mask.names import GLOBAL_REGEX, NAME_REGEX
from imperative_stitch.utils.def_use_mask.ordering import PythonNodeOrdering


@dataclass
class DefUseMaskConfiguration:
    pass


class DefUseChainPreorderMask(ns.PreorderMask):
    """
    Preorder mask that filters out symbols that are not defined at a given position.

    The idea is to have a stack of Handler objects, one for each node in the syntax tree.

    Args:
        tree_dist: The tree distribution that the mask is applied to.
        dsl: The domain-specific language that the mask is applied to.
    """

    def __init__(self, tree_dist, dsl):
        super().__init__(tree_dist)
        assert isinstance(tree_dist.ordering, PythonNodeOrdering)
        self.dsl = dsl
        self.has_global_available = any(
            GLOBAL_REGEX.match(x) for x, _ in self.tree_dist.symbols
        )
        self.handlers = []
        self.config = DefUseMaskConfiguration()

    def _matches(self, names, symbol_id):
        """
        Whether or not the symbol matches the names.
        """
        symbol, _ = self.tree_dist.symbols[symbol_id]
        if symbol == "Name~E":
            return self.has_global_available or len(names) > 0
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
        if handler.is_defining(position):
            return [True] * len(symbols)
        names = handler.currently_defined_names()
        return [self._matches(names, symbol) for symbol in symbols]

    def on_entry(self, position: int, symbol: int):
        """
        Updates the stack of handlers when entering a node.
        """
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
