from ..handler import Handler


class DefiningStatementHandler(Handler):
    # these fields must be defined in the subclass
    name: str = None
    children: dict[str, int] = None
    targeted: list[str] = None
    # the field after which the symbols are defined
    define_symbols_on_exit: str = None

    def __init__(self, mask, valid_symbols, config):
        super().__init__(mask, valid_symbols, config)
        assert isinstance(self.name, str)
        assert isinstance(self.children, dict)
        assert isinstance(self.targeted, list)
        assert isinstance(self.define_symbols_on_exit, str)
        self._targeted_positions = [self.children[child] for child in self.targeted]
        self.defined_symbols = set()

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if position in self._targeted_positions:
            return self.target_child(symbol)
        return super().on_child_enter(position, symbol)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        if position in self._targeted_positions:
            self.defined_symbols |= child.defined_symbols
        if position == self.children[self.define_symbols_on_exit]:
            self.valid_symbols |= self.defined_symbols
        super().on_child_exit(position, symbol, child)

    def is_defining(self, position: int) -> bool:
        return position in self._targeted_positions


class ChildFrameCreatorHandler(DefiningStatementHandler):
    def __init__(self, mask, valid_symbols, config):
        self.original_valid_symbols = valid_symbols
        super().__init__(mask, set(valid_symbols), config)


class AssignHandler(DefiningStatementHandler):
    name = "Assign~S"
    children = {"target": 0, "value": 1, "type_comment": 2}
    targeted = ["target"]
    define_symbols_on_exit = "type_comment"


class ForHandler(DefiningStatementHandler):
    name = "For~S"
    children = {"target": 0, "iter": 1, "body": 2, "orelse": 3}
    targeted = ["target"]
    define_symbols_on_exit = "iter"


class ImportHandler(DefiningStatementHandler):
    name = "Import~S"
    children = {"names": 0}
    targeted = ["names"]
    define_symbols_on_exit = "names"


class ImportFromHandler(ImportHandler):
    name = "ImportFrom~S"
    children = {"module": 0, "names": 1}


class LambdaHandler(ChildFrameCreatorHandler):
    name = "Lambda~E"
    children = {"args": 0, "body": 1}
    targeted = ["args"]
    define_symbols_on_exit = "args"
