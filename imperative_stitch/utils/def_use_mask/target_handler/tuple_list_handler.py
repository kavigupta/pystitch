from ..handler import Handler
from .target_handler import TargetConstructHandler


class TupleLHSHandler(TargetConstructHandler):
    """
    This is for LHS values where nothing is actually being defined (e.g., Subscript, Attribute, etc.)
    """

    name = "Tuple~L"

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if position == self.child_fields["elts"]:
            return self.target_child(symbol)
        return super().on_child_enter(position, symbol)

    def is_defining(self, position: int) -> bool:
        return position == self.child_fields["elts"]


class ListLHSHandler(TupleLHSHandler):
    name = "List~L"
