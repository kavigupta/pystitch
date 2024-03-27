from ..handler import Handler
from .target_handler import TargetConstructHandler, TargetHandler


class PassthroughLHSHandler(TargetHandler):
    """
    Pass through handler that does not collect any information,
        instead it just targets the children at the given indices.

    If indices is None, it will target all children.
    """

    indices: list[int] = None

    def child_is_targeted(self, position: int) -> bool:
        return self.indices is None or position in self.indices

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if self.child_is_targeted(position):
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
