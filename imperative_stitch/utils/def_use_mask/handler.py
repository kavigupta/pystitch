from abc import ABC, abstractmethod

from imperative_stitch.parser.parse_python import fields_for_node
from imperative_stitch.utils.def_use_mask.names import match_either


class Handler(ABC):
    def __init__(self, mask, valid_symbols, config):
        self.mask = mask
        self.valid_symbols = valid_symbols
        self.config = config

    @abstractmethod
    def on_enter(self):
        pass

    @abstractmethod
    def on_exit(self):
        pass

    @abstractmethod
    def on_child_enter(self, position: int, symbol: int) -> "Handler":
        from .defining_statement_handler import defining_statement_handlers

        symbol, _ = self.mask.tree_dist.symbols[symbol]
        return defining_statement_handlers().get(symbol, DefaultHandler)(
            self.mask, self.currently_defined_symbols(), self.config
        )

    @abstractmethod
    def on_child_exit(self, position: int, symbol: int, child: "Handler"):
        pass

    def currently_defined_symbols(self) -> set[int]:
        return self.valid_symbols

    @abstractmethod
    def is_defining(self, position: int) -> bool:
        pass

    def currently_defined_names(self):
        names = []
        for symbol in self.currently_defined_symbols():
            mat = match_either(self.mask.tree_dist.symbols[symbol][0])
            if not mat:
                raise ValueError(
                    f"Could not match {self.mask.tree_dist.symbols[symbol][0]}"
                )
            names.append(mat.group("name"))
        return names

    def target_child(self, symbol: int) -> "Handler":
        # pylint: disable=cyclic-import
        from .target_handler import handle_target

        return handle_target(symbol)(
            self.mask, self.currently_defined_symbols(), self.config
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
    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        return super().on_child_enter(position, symbol)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        pass

    def is_defining(self, position: int) -> bool:
        return False
