import copy
from dataclasses import dataclass
from typing import Dict, List

import neurosym as ns

from imperative_stitch.compress.abstraction import Abstraction
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
        self.matching_dbvar_level = 0
        self.dbvar_max_value = None
        self.dbvar_under_successor = None
        self.dbvar_value = None

    def _matches(self, names, symbol_id):
        """
        Whether or not the symbol matches the names.
        """
        symbol, _ = self.tree_dist.symbols[symbol_id]
        if symbol == "Name~E":
            return self.has_global_available or len(names) > 0
        if symbol == "dbvar~Name":
            return self.matching_dbvar_level == 0 and len(names) > 0
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
        if self.matching_dbvar_level > 0:
            mask = [False] * len(symbols)
            rendered_symbols = [self.tree_dist.symbols[sym][0] for sym in symbols]
            dbvar_symbols = {
                sym: i
                for i, sym in enumerate(rendered_symbols)
                if sym.startswith("dbvar-")
            }
            if self.dbvar_under_successor:
                mask[dbvar_symbols[f"dbvar-{self.de_bruijn_limit}~DBV"]] = True
                if "dbvar-successor~DBV" in dbvar_symbols:
                    mask[dbvar_symbols["dbvar-successor~DBV"]] = True
            else:
                start_at = 0 if is_defn else 1
                for i in range(start_at, self.dbvar_max_value + 1):
                    if i > self.de_bruijn_limit:
                        if "dbvar-successor~DBV" in dbvar_symbols:
                            mask[dbvar_symbols["dbvar-successor~DBV"]] = True
                        break
                    mask[dbvar_symbols[f"dbvar-{i}~DBV"]] = True
            return mask
        if is_defn:
            return [True] * len(symbols)
        names = handler.currently_defined_names()
        return [self._matches(names, symbol) for symbol in symbols]

    def on_entry(self, position: int, symbol: int):
        """
        Updates the stack of handlers when entering a node.
        """
        if self.tree_dist.symbols[symbol][0] == "dbvar~Name":
            assert self.matching_dbvar_level == 0
            self.matching_dbvar_level += 1
            self.dbvar_max_value = len(self.currently_defined_indices())
            self.dbvar_under_successor = False
            self.dbvar_value = 0
            return
        if self.matching_dbvar_level > 0:
            self.matching_dbvar_level += 1
            if self.tree_dist.symbols[symbol][0] == "dbvar-successor~DBV":
                self.dbvar_under_successor = True
                self.dbvar_value += 1
                self.dbvar_max_value -= 1
                return
            self.dbvar_value += int(
                self.tree_dist.symbols[symbol][0].split("-")[-1].split("~")[0]
            )
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
        from .canonicalize_de_bruijn import canonicalized_python_name_as_leaf

        if self.matching_dbvar_level > 0:
            self.matching_dbvar_level -= 1
            if self.matching_dbvar_level == 0:
                assert self.tree_dist.symbols[symbol][0] == "dbvar~Name"
                symbol = self.tree_dist.symbol_to_index[
                    canonicalized_python_name_as_leaf(
                        len(self.currently_defined_indices()) - self.dbvar_value,
                        use_type=True,
                    )
                ]
                self.dbvar_max_value = None
                self.dbvar_under_successor = None
                self.dbvar_value = None
                self.on_entry(position, symbol)
            else:
                return
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
