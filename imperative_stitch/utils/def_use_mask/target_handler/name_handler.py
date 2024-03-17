from ..handler import DefaultHandler, Handler


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

    def is_defining(self, position: int) -> bool:
        return position == self.fields["id"]
