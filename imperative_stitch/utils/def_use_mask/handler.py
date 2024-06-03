from abc import ABC, abstractmethod
from typing import Callable, List

import neurosym as ns

from imperative_stitch.utils.def_use_mask.names import VARIABLE_REGEX, match_either
from imperative_stitch.utils.def_use_mask.special_case_symbol_predicate import (
    SpecialCaseSymbolPredicate,
)


class Handler(ABC):
    """
    Corresponds to a given node in the ns.SExpression AST.
    Keeps track of a list of defined production indices,
        in order of definition.
    """

    def __init__(self, mask, defined_production_idxs, config):
        assert isinstance(defined_production_idxs, list)
        self.mask = mask
        self.defined_production_idxs = defined_production_idxs
        self.config = config

    @abstractmethod
    def on_child_enter(self, position: int, symbol: int) -> "Handler":
        """
        When a child is entered, this method is called to determine the handler.

        Args:
            position: The position in the s-expression.
            symbol: The symbol of the child (index into a grammar's symbols list)
                Note: this can include variables, e.g., const-&x:0-Name,
                   but it can also include production symbols like Assign~S
                   or other leaves like const-i2~Const.

        Returns:
            The handler for the child.
        """
        return default_handler(
            symbol, self.mask, self.currently_defined_indices(), self.config
        )

    @abstractmethod
    def on_child_exit(self, position: int, symbol: int, child: "Handler"):
        """
        When a child is exited, this method is called to perform tasks related
            to the child.
        """

    def currently_defined_indices(self) -> list[int]:
        """
        Returns the list of currently defined symbols, in order of definition.
        """
        assert isinstance(self.defined_production_idxs, list)
        return self.defined_production_idxs

    @abstractmethod
    def is_defining(self, position: int) -> bool:
        """
        Returns whether the context at the given position is defining.

        E.g., for an Assign node, the left-hand side is defining, and
            the right-hand side is not. This is important because for
            defining contexts, we do not need to use a previously
            defined variable.
        """

    def currently_defined_names(self):
        """
        Return the set of currently defined names. Note that this
            isn't the set of production symbols like const-&x:0-Name,
            but rather a set of names like x.
        """
        names = set()
        for symbol in self.currently_defined_indices():
            sym = self.mask.id_to_name(symbol)
            mat = match_either(sym)
            if not mat:
                assert VARIABLE_REGEX.match(sym), f"Could not match {sym}"
                continue
            names.add(mat.group("name"))
        return names

    def target_child(self, symbol: int) -> "Handler":
        """
        Return a handler collecting targets for the given child.
        """
        # pylint: disable=cyclic-import
        from .target_handler import create_target_handler

        return create_target_handler(
            symbol, self.mask, self.currently_defined_indices(), self.config
        )

    def _matches(self, names, symbol_id, special_case_predicates, idx_to_name):
        """
        Whether or not the symbol matches the names.
        """

        for pred in special_case_predicates:
            if pred.applies(symbol_id):
                return pred.compute_mask(symbol_id, names)
        if idx_to_name[symbol_id] is None:
            return True
        return idx_to_name[symbol_id] in names

    def compute_mask(
        self,
        position: int,
        symbols: List[int],
        special_case_predicates: List[SpecialCaseSymbolPredicate],
        idx_to_name: List[str],
    ):
        """
        Compute the mask for the given names. If the context is defining,
            then all symbols are valid. Otherwise, only the symbols that
            match the names are valid.
        """
        if self.is_defining(position):
            return [True] * len(symbols)
        names = set(self.currently_defined_names())
        return [
            self._matches(names, symbol, special_case_predicates, idx_to_name)
            for symbol in symbols
        ]


class ConstructHandler(Handler):
    """
    Handler for a single construct.
    """

    # must be overridden in subclasses, represents the name of the construct
    name: str = None

    def __init__(self, mask, defined_production_idxs, config):
        super().__init__(mask, defined_production_idxs, config)
        assert isinstance(self.name, str)
        self.child_fields = {
            field: i
            for i, field in enumerate(ns.python_ast_tools.fields_for_node(self.name))
        }


class DefaultHandler(Handler):
    def on_child_enter(self, position: int, symbol: int) -> Handler:
        return super().on_child_enter(position, symbol)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        pass

    def is_defining(self, position: int) -> bool:
        return False


def default_handler(symbol: int, mask, defined_production_idxs, config) -> Handler:
    # pylint: disable=cyclic-import
    from .defining_statement_handler import defining_statement_handlers

    assert isinstance(defined_production_idxs, list)

    symbol = mask.id_to_name(symbol)
    hook = config.get_hook(symbol)
    if hook is not None:
        return hook.pull_handler(
            symbol, mask, defined_production_idxs, config, handler_fn=default_handler
        )

    return defining_statement_handlers().get(symbol, DefaultHandler)(
        mask, defined_production_idxs, config
    )


class HandlerPuller(ABC):
    @abstractmethod
    def pull_handler(
        self, symbol: int, mask, defined_production_idxs, config, handler_fn: Callable
    ) -> Handler:
        pass
