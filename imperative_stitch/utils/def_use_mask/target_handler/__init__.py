from .alias_handler import AliasTargetHandler
from .list_handler import ListHandler
from .name_handler import NameTargetHandler
from .non_collecting_handler import NonCollectingTargetHandler


def targets_handler(mask, valid_symbols):
    targets_map = {
        "Name~L": NameTargetHandler,
        "arg~A": NameTargetHandler,
        "alias~alias": AliasTargetHandler,
        "const-None~A": NonCollectingTargetHandler,
    }

    def symbol_to_handler(symbol):
        symbol, _ = mask.tree_dist.symbols[symbol]
        if symbol.startswith("list"):
            return targets_handler
        return targets_map[symbol]

    return ListHandler(
        symbol_to_handler,
        mask,
        valid_symbols,
    )
