from ..handler import Handler


class ImportHandler(Handler):
    name = "Import~S"
    children = {"names": 0}

    def __init__(self, mask, valid_symbols, config):
        super().__init__(mask, valid_symbols, config)
        self.defined_symbols = set()

    def on_enter(self):
        pass

    def on_exit(self):
        self.valid_symbols |= self.defined_symbols

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if position == self.children["names"]:
            return self.target_child(symbol)
        return super().on_child_enter(position, symbol)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        if position == self.children["names"]:
            self.defined_symbols |= child.defined_symbols

    def is_defining(self, position: int) -> bool:
        return position == self.children["names"]


class ImportFromHandler(ImportHandler):
    name = "ImportFrom~S"
    children = {"module": 0, "names": 1}
