from abc import ABC, abstractmethod

from imperative_stitch.utils.def_use_mask.names import NAME_REGEX


class Handler(ABC):
    def __init__(self, mask, valid_symbols):
        self.mask = mask
        self.valid_symbols = valid_symbols

    @abstractmethod
    def on_enter(self):
        pass

    @abstractmethod
    def on_exit(self):
        pass

    @abstractmethod
    def on_child_enter(self, position: int, symbol: int) -> "Handler":
        pass

    @abstractmethod
    def on_child_exit(self, position: int, symbol: int, child: "Handler"):
        pass

    @abstractmethod
    def currently_defined_symbols(self) -> set[int]:
        pass

    @abstractmethod
    def is_defining(self, position: int) -> bool:
        pass

    def currently_defined_names(self):
        return [
            NAME_REGEX.match(self.mask.tree_dist.symbols[symbol][0]).group(1)
            for symbol in self.currently_defined_symbols()
        ]


class DefaultHandler(Handler):
    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        # pylint: disable=cyclic-import
        from imperative_stitch.utils.def_use_mask.defining_statement_handler import (
            defining_statement_handlers,
        )

        symbol, _ = self.mask.tree_dist.symbols[symbol]
        return defining_statement_handlers().get(symbol, DefaultHandler)(
            self.mask, self.valid_symbols
        )

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        pass

    def currently_defined_symbols(self) -> set[int]:
        return self.valid_symbols

    def is_defining(self, position: int) -> bool:
        return False
