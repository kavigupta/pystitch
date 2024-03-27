from ..handler import Handler
from .target_handler import TargetHandler


class TupleListLHSHandler(TargetHandler):
    """
    This is for LHS values where nothing is actually being defined (e.g., Subscript, Attribute, etc.)
    """

    fields = {"elts": 0}

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if position == self.fields["elts"]:
            return self.target_child(symbol)
        return super().on_child_enter(position, symbol)

    def is_defining(self, position: int) -> bool:
        return position == self.fields["elts"]
