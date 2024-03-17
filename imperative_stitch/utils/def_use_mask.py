import re
from abc import ABC, abstractmethod
from typing import List

import neurosym as ns

NAME_REGEX = re.compile(r"const-&(\w+):(\d+)~(Name|NameStr|NullableNameStr)")
GLOBAL_REGEX = re.compile(r"const-g_(\w+)~(Name|NameStr|NullableNameStr)")


class DefUseChainPreorderMask(ns.PreorderMask):
    def __init__(self, tree_dist, dsl):
        super().__init__(tree_dist)
        self.dsl = dsl
        self.has_global_available = any(
            GLOBAL_REGEX.match(x) for x, _ in self.tree_dist.symbols
        )
        self.handlers = []

    def _matches(self, handler, symbol_id):
        symbol, _ = self.tree_dist.symbols[symbol_id]
        names = handler.currently_defined_names()
        if symbol == "Name~E":
            return self.has_global_available or len(names) > 0
        mat = NAME_REGEX.match(symbol)
        if not mat:
            return True
        return mat.group(1) in names

    def compute_mask(self, position: int, symbols: List[int]) -> List[bool]:
        handler = self.handlers[-1]
        if handler.is_defining(position):
            return [True] * len(symbols)
        return [self._matches(handler, symbol) for symbol in symbols]

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


def targets_handler(mask, valid_symbols):
    targets_map = {
        "Name~L": NameTargetHandler,
        "arg~A": NameTargetHandler,
        "alias~alias": AliasTargetHandler,
        "const-None~A": NonCollectingTargetHandler,
    }

    def symbol_to_handler(symbol):
        symbol, _ = mask.tree_dist.symbols[symbol]
        if symbol.startswith("list"):
            return targets_handler
        return targets_map[symbol]

    return ListHandler(
        symbol_to_handler,
        mask,
        valid_symbols,
    )


class AssignmentHandler(Handler):
    name = "Assign~S"
    children = {"target": 0}

    def __init__(self, mask, valid_symbols):
        super().__init__(mask, valid_symbols)
        self.defined_symbols = set()

    def on_enter(self):
        pass

    def on_exit(self):
        self.valid_symbols |= self.defined_symbols

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if position == self.children["target"]:
            return targets_handler(self.mask, self.valid_symbols)
        return DefaultHandler(self.mask, self.valid_symbols)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        if position == self.children["target"]:
            self.defined_symbols |= child.defined_symbols

    def currently_defined_symbols(self) -> set[int]:
        return self.valid_symbols

    def is_defining(self, position: int) -> bool:
        return position == self.children["target"]


class ImportHandler(Handler):
    name = "Import~S"
    children = {"names": 0}

    def __init__(self, mask, valid_symbols):
        super().__init__(mask, valid_symbols)
        self.defined_symbols = set()

    def on_enter(self):
        pass

    def on_exit(self):
        self.valid_symbols |= self.defined_symbols

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if position == self.children["names"]:
            return targets_handler(self.mask, self.valid_symbols)
        return DefaultHandler(self.mask, self.valid_symbols)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        if position == self.children["names"]:
            self.defined_symbols |= child.defined_symbols

    def currently_defined_symbols(self) -> set[int]:
        return self.valid_symbols

    def is_defining(self, position: int) -> bool:
        return position == self.children["names"]


class ListHandler(Handler):
    def __init__(self, handler_type, mask, valid_symbols, *args):
        super().__init__(mask, valid_symbols)
        self.handlers = {}
        self.handler_type = handler_type
        self.args = args

    @property
    def defined_symbols(self):
        return {
            symbol
            for handler in self.handlers.values()
            for symbol in handler.defined_symbols
        }

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        self.handlers[position] = self.handler_type(symbol)(
            self.mask, self.valid_symbols, *self.args
        )
        return self.handlers[position]

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        pass

    def currently_defined_symbols(self) -> set[int]:
        return self.valid_symbols

    def is_defining(self, position: int) -> bool:
        return True


class FuncDefHandler(Handler):
    name = "FunctionDef~S"
    fields = {"name": 0, "args": 1, "body": 2}

    def __init__(self, mask, valid_symbols):
        self.original_valid_symbols = valid_symbols
        super().__init__(mask, set(valid_symbols))
        self.name = None

    def on_enter(self):
        pass

    def on_exit(self):
        assert self.name is not None
        self.original_valid_symbols.add(self.name)

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if position == self.fields["name"]:
            self.name = symbol
            self.valid_symbols.add(symbol)
        if position == self.fields["args"]:
            return targets_handler(self.mask, self.valid_symbols)
        return DefaultHandler(self.mask, self.valid_symbols)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        if position == self.fields["args"]:
            for handler in child.handlers.values():
                self.valid_symbols |= handler.defined_symbols

    def currently_defined_symbols(self) -> set[int]:
        return self.valid_symbols

    def is_defining(self, position: int) -> bool:
        return position in {self.fields["name"], self.fields["args"]}


class DefaultHandler(Handler):
    statement_handlers = {
        x.name: x for x in [AssignmentHandler, ImportHandler, FuncDefHandler]
    }

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

    def currently_defined_symbols(self) -> set[int]:
        return self.valid_symbols

    def is_defining(self, position: int) -> bool:
        return False


class NameTargetHandler(Handler):
    # this works for both Name and arg
    fields = {"id": 0, "arg": 0}

    def __init__(self, mask, valid_symbols):
        super().__init__(mask, valid_symbols)
        self.defined_symbols = set()

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if position == self.fields["id"]:
            self.defined_symbols.add(symbol)
        return DefaultHandler(self.mask, self.valid_symbols)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        pass

    def currently_defined_symbols(self) -> set[int]:
        return self.valid_symbols

    def is_defining(self, position: int) -> bool:
        return position == self.fields["id"]


class AliasTargetHandler(Handler):
    fields = {"name": 0, "asname": 1}

    def __init__(self, mask, valid_symbols):
        super().__init__(mask, valid_symbols)
        self.defined_symbols = set()

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        # since we hit name first, we can just overwrite the defined_symbols
        # since asname overwrites name
        if self.mask.tree_dist.symbols[symbol][0] != "const-None~NullableNameStr":
            self.defined_symbols = {symbol}

        return DefaultHandler(self.mask, self.valid_symbols)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        pass

    def currently_defined_symbols(self) -> set[int]:
        return self.valid_symbols

    def is_defining(self, position: int) -> bool:
        # both name and asname are defining
        return True


class NonCollectingTargetHandler(Handler):
    @property
    def defined_symbols(self):
        return set()

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        return DefaultHandler(self.mask, self.valid_symbols)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        pass

    def currently_defined_symbols(self) -> set[int]:
        return self.valid_symbols

    def is_defining(self, position: int) -> bool:
        return False
