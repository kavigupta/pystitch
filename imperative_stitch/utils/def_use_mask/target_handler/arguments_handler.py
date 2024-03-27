from ..handler import Handler
from .target_handler import TargetConstructHandler


class ArgumentsHandler(TargetConstructHandler):
    name = "arguments~As"

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if self.is_defining(position):
            return self.target_child(symbol)
        return super().on_child_enter(position, symbol)

    def is_defining(self, position: int) -> bool:
        # both name and asname are defining
        return position not in {
            self.child_fields["kw_defaults"],
            self.child_fields["defaults"],
        }
