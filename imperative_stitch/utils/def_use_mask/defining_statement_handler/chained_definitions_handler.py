from ..handler import Handler


class ChainedDefinitionsHandler(Handler):
    # handled out of order. generators first

    def __init__(self, mask, valid_symbols, config, children):
        # copy the valid symbols so changes don't affect the parent
        super().__init__(mask, set(valid_symbols), config)
        self.defined_symbols = set()
        self.children = children

    def on_enter(self):
        pass

    def on_exit(self):
        # automatically resets
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if position == self.children["generators"]:
            return GeneratorsHandler(self.mask, self.valid_symbols, self.config)
        return super().on_child_enter(position, symbol)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        pass

    def is_defining(self, position: int) -> bool:
        return False


class ListComprehensionHandler(ChainedDefinitionsHandler):
    name = "ListComp~E"

    def __init__(self, mask, valid_symbols, config):
        super().__init__(mask, valid_symbols, config, {"elt": 0, "generators": 1})


class SetComprehensionHandler(ListComprehensionHandler):
    name = "SetComp~E"


class GeneratorExprHandler(ListComprehensionHandler):
    name = "GeneratorExp~E"


class DictComprehensionHandler(ChainedDefinitionsHandler):
    name = "DictComp~E"

    def __init__(self, mask, valid_symbols, config):
        super().__init__(
            mask, valid_symbols, config, {"key": 0, "value": 1, "generators": 2}
        )


class GeneratorsHandler(Handler):
    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        return ComprehensionHandler(self.mask, self.valid_symbols, self.config)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        pass

    def is_defining(self, position: int) -> bool:
        return False


class ComprehensionHandler(Handler):
    fields = {"target": 0, "iter": 1, "ifs": 2}

    def __init__(self, mask, valid_symbols, config):
        super().__init__(mask, valid_symbols, config)
        self.defined_symbols = None

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if position == self.fields["target"]:
            return self.target_child(symbol)
        return super().on_child_enter(position, symbol)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        if position == self.fields["target"]:
            assert self.defined_symbols is None
            self.defined_symbols = child.defined_symbols
        if position == self.fields["iter"]:
            assert self.defined_symbols is not None
            # now done with the iter field
            # we should allow the defined symbols to be used
            self.valid_symbols |= self.defined_symbols

    def is_defining(self, position: int) -> bool:
        return position == self.fields["target"]


chained_definition_handlers = [
    ListComprehensionHandler,
    SetComprehensionHandler,
    GeneratorExprHandler,
    DictComprehensionHandler,
]
