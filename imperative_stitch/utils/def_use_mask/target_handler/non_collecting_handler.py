from ..handler import Handler
from .target_handler import TargetHandler


class NonCollectingTargetHandler(TargetHandler):
    """
    This is for LHS values where nothing is actually being defined (e.g., Subscript, Attribute, etc.)
    """

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        return super().on_child_enter(position, symbol)

    def is_defining(self, position: int) -> bool:
        return False
