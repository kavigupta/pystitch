from ..handler import DefaultHandler, Handler
from ..target_handler import targets_handler


class AssignHandler(Handler):
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
