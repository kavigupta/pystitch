import ast

from ..handler import Handler
from .target_handler import TargetHandler


class ArgumentsHandler(TargetHandler):
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

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if self.is_defining(position):
            return self.target_child(symbol)
        return super().on_child_enter(position, symbol)

    def is_defining(self, position: int) -> bool:
        # both name and asname are defining
        return position not in {self.fields["kw_defaults"], self.fields["defaults"]}
