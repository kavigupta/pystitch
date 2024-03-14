from abc import ABC, abstractmethod
import re
from typing import List
import neurosym as ns

NAME_REGEX = re.compile(r"const-&(\w+):(\d+)~Name")


class DefUseChainPreorderMask(ns.PreorderMask):
    def __init__(self, tree_dist, dsl):
        super().__init__(tree_dist)
        self.dsl = dsl
        self.handlers = []

    def compute_mask(self, position: int, symbols: List[int]) -> List[bool]:
        handler = self.handlers[-1]
        if handler.is_defining(position):
            return [True] * len(symbols)
        mask = []
        for symbol_id in symbols:
            symbol, _ = self.tree_dist.symbols[symbol_id]
            mat = NAME_REGEX.match(symbol)
            if not mat:
                mask.append(True)
                continue
            mask.append(symbol_id in handler.currently_defined_names())
        return mask

    def on_entry(self, position: int, symbol: int):
        print("handlers", self.handlers)
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


class Handler(ABC):

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
    def currently_defined_names(self) -> set[str]:
        pass

    @abstractmethod
    def is_defining(self, position: int) -> bool:
        pass


def targets_handler(mask, valid_symbols):
    targets_map = {
        "Name~L": NameTargetHandler,
    }
    return ListHandler(
        lambda symbol: targets_map[mask.tree_dist.symbols[symbol][0]],
        mask,
        valid_symbols,
    )


class AssignmentHandler(Handler):
    name = "Assign~S"
    children = {"target": 0}

    def __init__(self, mask, valid_symbols):
        self.mask = mask
        self.valid_symbols = valid_symbols
        self.defined_symbols = set()

    def on_enter(self):
        pass

    def on_exit(self):
        print("EXITING ASSIGNMENT", self.defined_symbols)
        self.valid_symbols |= self.defined_symbols

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        print("entering assignment child", position)
        if position == self.children["target"]:
            return targets_handler(self.mask, self.valid_symbols)
        return DefaultHandler(self.mask, self.valid_symbols)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        print("exiting assignment child", position)
        if position == self.children["target"]:
            print(child.handlers)
            target_handlers = child.handlers.values()
            for handler in target_handlers:
                print("TARGET HANDLER", handler.defined_symbols)
                self.defined_symbols |= handler.defined_symbols

    def currently_defined_names(self) -> set[str]:
        return self.valid_symbols

    def is_defining(self, position: int) -> bool:
        return False


class ListHandler(Handler):

    def __init__(self, handler_type, mask, valid_symbols, *args):
        self.handlers = {}
        self.handler_type = handler_type
        self.mask = mask
        self.valid_symbols = valid_symbols
        self.args = args

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        print("new handler for", self)
        self.handlers[position] = self.handler_type(symbol)(
            self.mask, self.valid_symbols, *self.args
        )
        return self.handlers[position]

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        pass

    def currently_defined_names(self) -> set[str]:
        return self.valid_symbols

    def is_defining(self, position: int) -> bool:
        return False


class DefaultHandler(Handler):

    statement_handlers = {
        x.name: x
        for x in [
            AssignmentHandler,
        ]
    }

    def __init__(self, mask, valid_symbols):
        self.mask = mask
        self.valid_symbols = valid_symbols

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        symbol, _ = self.mask.tree_dist.symbols[symbol]
        return self.statement_handlers.get(symbol, DefaultHandler)(
            self.mask, self.valid_symbols
        )

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        pass

    def currently_defined_names(self) -> set[str]:
        return self.valid_symbols

    def is_defining(self, position: int) -> bool:
        return False


class NameTargetHandler(Handler):
    fields = {"id": 0}

    def __init__(self, mask, valid_symbols):
        self.mask = mask
        self.valid_symbols = valid_symbols
        self.defined_symbols = set()

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        print("NAME TARGET")
        if position == self.fields["id"]:
            self.defined_symbols.add(symbol)
        return DefaultHandler(self.mask, self.valid_symbols)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        pass

    def currently_defined_names(self) -> set[str]:
        return self.valid_symbols

    def is_defining(self, position: int) -> bool:
        return position == self.fields["id"]
