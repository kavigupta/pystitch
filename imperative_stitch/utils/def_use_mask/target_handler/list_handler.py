from ..handler import Handler


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

    def is_defining(self, position: int) -> bool:
        return True
