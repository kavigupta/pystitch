from .handler import ConstructHandler, Handler


def handle_target(root_symbol: int):
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

    def dispatch(mask, valid_symbols, config):
        symbol = root_symbol
        symbol, _ = mask.tree_dist.symbols[symbol]
        if symbol.startswith("list"):
            return PassthroughLHSHandler(mask, valid_symbols, config)
        return targets_map[symbol](mask, valid_symbols, config)

    return dispatch


class TargetHandler(Handler):
    def __init__(self, mask, valid_symbols, config):
        super().__init__(mask, valid_symbols, config)
        self.defined_symbols = set()

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        if hasattr(child, "defined_symbols"):
            self.defined_symbols.update(child.defined_symbols)


class TargetConstructHandler(TargetHandler, ConstructHandler):
    def __init__(self, mask, valid_symbols, config):
        TargetHandler.__init__(self, mask, valid_symbols, config)
        ConstructHandler.__init__(self, mask, valid_symbols, config)


class PassthroughLHSHandler(TargetHandler):
    """
    Pass through handler that does not collect any information,
        instead it just targets the children at the given indices.

    If indices is None, it will target all children.
    """

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if self.is_defining(position):
            return self.target_child(symbol)
        return super().on_child_enter(position, symbol)

    def is_defining(self, position: int) -> bool:
        return True


class PassthroughLHSConstructHandler(PassthroughLHSHandler, TargetConstructHandler):
    use_fields: list[str] = None

    def __init__(self, mask, valid_symbols, config):
        PassthroughLHSHandler.__init__(self, mask, valid_symbols, config)
        TargetConstructHandler.__init__(self, mask, valid_symbols, config)

        self.indices = [self.child_fields[x] for x in self.use_fields]

    def is_defining(self, position: int) -> bool:
        return self.indices is None or position in self.indices


class NonCollectingTargetHandler(PassthroughLHSHandler):
    """
    This is for LHS values where nothing is actually being defined (e.g., Subscript, Attribute, etc.)
    """

    def is_defining(self, position: int) -> bool:
        return False


class StarredHandler(PassthroughLHSConstructHandler):
    name = "Starred~L"
    use_fields = ["value"]


class ArgumentsHandler(PassthroughLHSConstructHandler):
    name = "arguments~As"
    use_fields = ("posonlyargs", "args", "vararg", "kwonlyargs", "kwarg")


class TupleLHSHandler(PassthroughLHSConstructHandler):
    """
    This is for LHS values where nothing is actually being defined (e.g., Subscript, Attribute, etc.)
    """

    name = "Tuple~L"
    use_fields = ["elts"]


class ListLHSHandler(TupleLHSHandler):
    name = "List~L"


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
