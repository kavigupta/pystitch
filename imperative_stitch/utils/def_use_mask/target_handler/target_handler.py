from ..handler import Handler


class TargetHandler(Handler):
    def __init__(self, mask, valid_symbols, config):
        super().__init__(mask, valid_symbols, config)
        self.defined_symbols = set()

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        if isinstance(child, TargetHandler):
            self.defined_symbols.update(child.defined_symbols)
