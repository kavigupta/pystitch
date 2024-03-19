from typing import List

import neurosym as ns

from imperative_stitch.utils.def_use_mask.handler import DefaultHandler
from imperative_stitch.utils.def_use_mask.names import GLOBAL_REGEX, NAME_REGEX
from imperative_stitch.utils.def_use_mask.ordering import PythonNodeOrdering


class DefUseChainPreorderMask(ns.PreorderMask):
    def __init__(self, tree_dist, dsl):
        super().__init__(tree_dist)
        assert isinstance(tree_dist.ordering, PythonNodeOrdering)
        self.dsl = dsl
        self.has_global_available = any(
            GLOBAL_REGEX.match(x) for x, _ in self.tree_dist.symbols
        )
        self.handlers = []

    def _matches(self, names, symbol_id):
        symbol, _ = self.tree_dist.symbols[symbol_id]
        if symbol == "Name~E":
            return self.has_global_available or len(names) > 0
        mat = NAME_REGEX.match(symbol)
        if not mat:
            return True
        return mat.group("name") in names

    def compute_mask(self, position: int, symbols: List[int]) -> List[bool]:
        handler = self.handlers[-1]
        if handler.is_defining(position):
            return [True] * len(symbols)
        names = handler.currently_defined_names()
        return [self._matches(names, symbol) for symbol in symbols]

    def on_entry(self, position: int, symbol: int):
        if not self.handlers:
            assert position == symbol == 0
            self.handlers.append(DefaultHandler(self, set()))
        else:
            self.handlers.append(self.handlers[-1].on_child_enter(position, symbol))

        self.handlers[-1].on_enter()

    def on_exit(self, position: int, symbol: int):
        self.handlers[-1].on_exit()
        popped = self.handlers.pop()
        if not self.handlers:
            assert position == symbol == 0
            return
        self.handlers[-1].on_child_exit(position, symbol, popped)
