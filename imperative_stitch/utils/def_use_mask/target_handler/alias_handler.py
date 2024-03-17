from ..handler import DefaultHandler, Handler


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

    def is_defining(self, position: int) -> bool:
        # both name and asname are defining
        return True
