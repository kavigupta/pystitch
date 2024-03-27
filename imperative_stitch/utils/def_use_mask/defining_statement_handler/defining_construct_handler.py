from ..handler import Handler
from .defining_statement_handler import ChildFrameCreatorHandler


class DefiningConstructHandler(ChildFrameCreatorHandler):
    """
    Handles defining constructs like function and class definitions.

    These are constructs that have a child frame defined as the body of the construct,
        as well as a name that is defined in the parent frame.
    """

    # these fields must be defined in the subclass
    construct_name_field: str = None

    def __init__(self, mask, valid_symbols, config):
        super().__init__(mask, valid_symbols, config)
        self._item_name = None
        assert isinstance(self.construct_name_field, str)

    def on_enter(self):
        pass

    def on_exit(self):
        assert self._item_name is not None
        self.original_valid_symbols.add(self._item_name)

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if (
            self.construct_name_field is not None
            and position == self.child_fields[self.construct_name_field]
        ):
            self._item_name = symbol
            self.valid_symbols.add(symbol)
        return super().on_child_enter(position, symbol)

    def is_defining(self, position: int) -> bool:
        if position == self.child_fields[self.construct_name_field]:
            return True
        return super().is_defining(position)


class FuncDefHandler(DefiningConstructHandler):
    name = "FunctionDef~S"
    targeted = ["args"]
    define_symbols_on_exit = "args"
    construct_name_field = "name"


class ClassDefHandler(DefiningConstructHandler):
    name = "ClassDef~S"
    targeted = []
    define_symbols_on_exit = "decorator_list"
    construct_name_field = "name"


defining_construct_handler = [FuncDefHandler, ClassDefHandler]
