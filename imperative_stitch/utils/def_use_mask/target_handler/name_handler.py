from ..handler import Handler
from .target_handler import TargetConstructHandler


class NameTargetHandler(TargetConstructHandler):
    name = "Name~Name"
    name_node = "id"

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if position == self.child_fields[self.name_node]:
            self.defined_symbols.add(symbol)
        return super().on_child_enter(position, symbol)

    def is_defining(self, position: int) -> bool:
        return position == self.child_fields[self.name_node]


class ArgTargetHandler(NameTargetHandler):
    name = "arg~arg"
    name_node = "arg"
