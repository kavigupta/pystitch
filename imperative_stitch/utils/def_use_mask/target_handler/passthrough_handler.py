from ..handler import Handler


class PassthroughLHSHandler(Handler):
    def __init__(self, mask, valid_symbols, config):
        super().__init__(mask, valid_symbols, config)
        self.defined_symbols = set()

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        return self.target_child(symbol)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        self.defined_symbols |= child.defined_symbols

    def is_defining(self, position: int) -> bool:
        return True
