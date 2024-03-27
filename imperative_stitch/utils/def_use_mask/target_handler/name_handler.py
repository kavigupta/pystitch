from ..handler import Handler
from .target_handler import TargetConstructHandler


class NameTargetHandler(TargetConstructHandler):
    name = "Name~Name"
    # will select the last of these that is defined
    name_nodes = {"id"}

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if self.is_defining(position):
            # for alias, we don't want to keep None
            if self.mask.tree_dist.symbols[symbol][0] != "const-None~NullableNameStr":
                self.defined_symbols = {symbol}
        return super().on_child_enter(position, symbol)

    def is_defining(self, position: int) -> bool:
        return any(position == self.child_fields[x] for x in self.name_nodes)


class ArgTargetHandler(NameTargetHandler):
    name = "arg~arg"
    name_nodes = {"arg"}


class AliasTargetHandler(NameTargetHandler):
    name = "alias~alias"
    name_nodes = {"name", "asname"}
