from ..handler import Handler
from .target_handler import TargetHandler


class AliasTargetHandler(TargetHandler):
    fields = {"name": 0, "asname": 1}

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        # since we hit name first, we can just overwrite the defined_symbols
        # since asname overwrites name
        if self.mask.tree_dist.symbols[symbol][0] != "const-None~NullableNameStr":
            self.defined_symbols = {symbol}

        return super().on_child_enter(position, symbol)

    def is_defining(self, position: int) -> bool:
        # both name and asname are defining
        return True
