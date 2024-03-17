from ..handler import DefaultHandler, Handler


class TupleListLHSHandler(Handler):
    """
    This is for LHS values where nothing is actually being defined (e.g., Subscript, Attribute, etc.)
    """

    fields = {"elts": 0}

    def __init__(self, mask, valid_symbols):
        super().__init__(mask, valid_symbols)
        self.defined_symbols = set()

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        # pylint: disable=cyclic-import
        from . import targets_handler

        if position == self.fields["elts"]:
            return targets_handler(self.mask, self.valid_symbols)
        return DefaultHandler(self.mask, self.valid_symbols)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        if position == self.fields["elts"]:
            target_handlers = child.handlers.values()
            for handler in target_handlers:
                self.defined_symbols |= handler.defined_symbols

    def currently_defined_symbols(self) -> set[int]:
        return self.valid_symbols

    def is_defining(self, position: int) -> bool:
        return position == self.fields["elts"]
