from .name_handler import NameTargetHandler, ArgTargetHandler, AliasTargetHandler
from .non_collecting_handler import NonCollectingTargetHandler
from .passthrough_handler import (
    PassthroughLHSHandler,
    StarredHandler,
    ArgumentsHandler,
    TupleLHSHandler,
    ListLHSHandler,
)

targets_map = {
    "Name~L": NameTargetHandler,
    "arg~A": ArgTargetHandler,
    "alias~alias": AliasTargetHandler,
    "const-None~A": NonCollectingTargetHandler,
    "Subscript~L": NonCollectingTargetHandler,
    "Attribute~L": NonCollectingTargetHandler,
    "Tuple~L": TupleLHSHandler,
    "List~L": ListLHSHandler,
    "_starred_content~L": PassthroughLHSHandler,
    "_starred_starred~L": PassthroughLHSHandler,
    "Starred~L": StarredHandler,
    "arguments~As": ArgumentsHandler,
}


def handle_target(root_symbol: int):
    def dispatch(mask, valid_symbols, config):
        symbol = root_symbol
        symbol, _ = mask.tree_dist.symbols[symbol]
        if symbol.startswith("list"):
            return PassthroughLHSHandler(mask, valid_symbols, config)
        return targets_map[symbol](mask, valid_symbols, config)

    return dispatch
