from imperative_stitch.utils.def_use_mask.target_handler.arguments_handler import (
    ArgumentsHandler,
)

from .alias_handler import AliasTargetHandler
from .name_handler import NameTargetHandler, ArgTargetHandler
from .non_collecting_handler import NonCollectingTargetHandler
from .passthrough_handler import PassthroughLHSHandler, StarredHandler
from .tuple_list_handler import TupleLHSHandler, ListLHSHandler

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
