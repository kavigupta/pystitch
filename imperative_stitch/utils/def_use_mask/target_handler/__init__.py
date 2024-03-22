from imperative_stitch.utils.def_use_mask.target_handler.arguments_handler import (
    ArgumentsHandler,
)

from .alias_handler import AliasTargetHandler
from .just_expression_handler import JustAnExpressionHandler
from .name_handler import NameTargetHandler
from .non_collecting_handler import NonCollectingTargetHandler
from .passthrough_handler import PassthroughLHSHandler, StarredHandler
from .tuple_list_handler import TupleListLHSHandler

targets_map = {
    "Name~L": NameTargetHandler,
    "arg~A": NameTargetHandler,
    "alias~alias": AliasTargetHandler,
    "const-None~A": NonCollectingTargetHandler,
    "Subscript~L": JustAnExpressionHandler,
    "Attribute~L": JustAnExpressionHandler,
    "Tuple~L": TupleListLHSHandler,
    "List~L": TupleListLHSHandler,
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
