from abc import ABC, abstractmethod

from imperative_stitch.parser.parse_python import fields_for_node
from imperative_stitch.utils.def_use_mask.names import match_either


class Handler(ABC):
    """
    Represents a handler that updates the set of valid symbols for
        a given position in the s-expression in the syntax tree.
    """

    def __init__(self, mask, valid_symbols, config):
        self.mask = mask
        self.valid_symbols = valid_symbols
        self.config = config

    @abstractmethod
    def on_child_enter(self, position: int, symbol: int) -> "Handler":
        return DefaultHandler.of(
            self.mask, self.currently_defined_symbols(), self.config, symbol
        )

    @abstractmethod
    def on_child_exit(self, position: int, symbol: int, child: "Handler"):
        """
        When a child is exited, this method is called to perform tasks related
            to the child.
        """

    def currently_defined_symbols(self) -> set[int]:
        """
        Returns the set of currently defined symbols.
        """
        return self.valid_symbols

    @abstractmethod
    def is_defining(self, position: int) -> bool:
        """
        Returns whether the construct at the given position is defining.
        """

    def currently_defined_names(self):
        """
        Return the set of currently defined names.
        """
        names = set()
        for symbol in self.currently_defined_symbols():
            mat = match_either(self.mask.tree_dist.symbols[symbol][0])
            if not mat:
                raise ValueError(
                    f"Could not match {self.mask.tree_dist.symbols[symbol][0]}"
                )
            names.add(mat.group("name"))
        return names

    def target_child(self, symbol: int) -> "Handler":
        """
        Return a handler collecting targets for the given child.
        """
        # pylint: disable=cyclic-import
        from .target_handler import create_target_handler

        return create_target_handler(
            symbol, self.mask, self.currently_defined_symbols(), self.config
        )


class ConstructHandler(Handler):
    """
    Handler for a single construct.
    """

    # must be overridden in subclasses, represents the name of the construct
    name: str = None

    def __init__(self, mask, valid_symbols, config):
        super().__init__(mask, valid_symbols, config)
        assert isinstance(self.name, str)
        self.child_fields = {
            field: i for i, field in enumerate(fields_for_node(self.name))
        }


class DefaultHandler(Handler):
    @classmethod
    def of(cls, mask, valid_symbols, config, symbol: int):
        return default_handler(symbol, mask, valid_symbols, config)

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        return super().on_child_enter(position, symbol)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        pass

    def is_defining(self, position: int) -> bool:
        return False


def default_handler(symbol: int, mask, valid_symbols, config) -> Handler:
    # pylint: disable=cyclic-import
    from .abstraction_handler import AbstractionHandler
    from .defining_statement_handler import defining_statement_handlers

    symbol, _ = mask.tree_dist.symbols[symbol]
    if symbol.startswith("fn_"):
        return AbstractionHandler(mask, valid_symbols, config, symbol)

    return defining_statement_handlers().get(symbol, DefaultHandler)(
        mask, valid_symbols, config
    )
