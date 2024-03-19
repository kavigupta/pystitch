from ..handler import Handler


class AssignHandler(Handler):
    name = "Assign~S"
    children = {"target": 0}

    def __init__(self, mask, valid_symbols, config):
        super().__init__(mask, valid_symbols, config)
        self.defined_symbols = set()

    def on_enter(self):
        pass

    def on_exit(self):
        self.valid_symbols |= self.defined_symbols

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if position == self.children["target"]:
            return self.target_child(symbol)
        print("assign, symbol", symbol, "position", position)
        return super().on_child_enter(position, symbol)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        if position == self.children["target"]:
            self.defined_symbols |= child.defined_symbols

    def is_defining(self, position: int) -> bool:
        return position == self.children["target"]
