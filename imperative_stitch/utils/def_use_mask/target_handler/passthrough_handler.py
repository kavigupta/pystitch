from ..handler import Handler


class PassthroughLHSHandler(Handler):
    def __init__(self, mask, valid_symbols):
        super().__init__(mask, valid_symbols)
        self.defined_symbols = set()

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        # pylint: disable=cyclic-import
        from . import targets_map

        return targets_map[self.mask.tree_dist.symbols[symbol][0]](
            self.mask, self.valid_symbols
        )

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        self.defined_symbols |= child.defined_symbols

    def is_defining(self, position: int) -> bool:
        return True
