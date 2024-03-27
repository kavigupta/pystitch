from ..handler import Handler
from .target_handler import TargetHandler


class NameTargetHandler(TargetHandler):
    # this works for Name, arg, and Starred
    fields = {"id": 0, "arg": 0, "value": 0}

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if position == self.fields["id"]:
            self.defined_symbols.add(symbol)
        return super().on_child_enter(position, symbol)

    def is_defining(self, position: int) -> bool:
        return position == self.fields["id"]
