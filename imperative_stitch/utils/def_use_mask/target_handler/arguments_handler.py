import ast

from ..handler import Handler


class ArgumentsHandler(Handler):
    assert ast.arguments._fields == (
        "posonlyargs",
        "args",
        "vararg",
        "kwonlyargs",
        "kw_defaults",
        "kwarg",
        "defaults",
    )
    fields = {
        "posonlyargs": 0,
        "args": 1,
        "vararg": 2,
        "kwonlyargs": 3,
        "kw_defaults": 4,
        "kwarg": 5,
        "defaults": 6,
    }

    def __init__(self, mask, valid_symbols):
        super().__init__(mask, valid_symbols)
        self.defined_symbols = set()

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if self.is_defining(position):
            return self.target_child(symbol)
        return super().on_child_enter(position, symbol)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        if self.is_defining(position):
            self.defined_symbols.update(child.defined_symbols)

    def is_defining(self, position: int) -> bool:
        # both name and asname are defining
        return position not in {self.fields["kw_defaults"], self.fields["defaults"]}
