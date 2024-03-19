from abc import ABC, abstractmethod

from imperative_stitch.utils.def_use_mask.names import match_either


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
        return DefaultHandler.of(self.mask, self.valid_symbols, symbol)

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

        return handle_target(symbol)(self.mask, self.valid_symbols)


class DefaultHandler(Handler):
    @classmethod
    def of(cls, mask, valid_symbols, symbol: int):
        # pylint: disable=cyclic-import
        from imperative_stitch.utils.def_use_mask.defining_statement_handler import (
            defining_statement_handlers,
        )

        symbol, _ = mask.tree_dist.symbols[symbol]
        return defining_statement_handlers().get(symbol, DefaultHandler)(
            mask, valid_symbols
        )

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        return self.of(self.mask, self.valid_symbols, symbol)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        pass

    def is_defining(self, position: int) -> bool:
        return False
