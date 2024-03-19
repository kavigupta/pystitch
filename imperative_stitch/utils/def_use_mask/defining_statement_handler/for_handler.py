from ..handler import Handler


class ForHandler(Handler):
    name = "For~S"
    children = {"target": 0, "iter": 1, "body": 2, "orelse": 3}

    def __init__(self, mask, valid_symbols):
        super().__init__(mask, valid_symbols)
        self.defined_symbols = set()

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if position == self.children["target"]:
            return self.target_child(symbol)
        return super().on_child_enter(position, symbol)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        if position == self.children["target"]:
            self.defined_symbols |= child.defined_symbols
        if position == self.children["iter"]:
            # done with the iter field, so we can use the defined symbols
            self.valid_symbols |= self.defined_symbols

    def is_defining(self, position: int) -> bool:
        return position == self.children["target"]
