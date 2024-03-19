from .alias_handler import AliasTargetHandler
from .just_expression_handler import JustAnExpressionHandler
from .list_handler import ListHandler
from .name_handler import NameTargetHandler
from .non_collecting_handler import NonCollectingTargetHandler
from .passthrough_handler import PassthroughLHSHandler
from .tuple_list_handler import TupleListLHSHandler


def targets_handler(mask, valid_symbols):
    return ListHandler(handle_target, mask, valid_symbols)


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
    "arguments~As": targets_handler,
}


def handle_target(root_symbol: int):
    def dispatch(mask, valid_symbols):
        symbol = root_symbol
        symbol, _ = mask.tree_dist.symbols[symbol]
        if symbol.startswith("list"):
            return targets_handler(mask, valid_symbols)
        return targets_map[symbol](mask, valid_symbols)

    return dispatch
