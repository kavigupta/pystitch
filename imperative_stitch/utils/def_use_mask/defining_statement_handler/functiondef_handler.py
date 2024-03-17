from ..handler import DefaultHandler, Handler
from ..target_handler import targets_handler


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
