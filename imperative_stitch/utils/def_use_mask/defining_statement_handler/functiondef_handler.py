from ..handler import Handler
from .defining_statement_handler import ChildFrameCreatorHandler


class DefiningConstructHandler(ChildFrameCreatorHandler):
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
            and position == self.children[self.construct_name_field]
        ):
            self._item_name = symbol
            self.valid_symbols.add(symbol)
        return super().on_child_enter(position, symbol)

    def is_defining(self, position: int) -> bool:
        if position == self.children[self.construct_name_field]:
            return True
        return super().is_defining(position)


class FuncDefHandler(DefiningConstructHandler):
    name = "FunctionDef~S"
    children = {"name": 0, "args": 1, "body": 2}
    targeted = ["args"]
    define_symbols_on_exit = "args"
    construct_name_field = "name"


class LambdaHandler(ChildFrameCreatorHandler):
    name = "Lambda~E"
    children = {"args": 0, "body": 1}
    targeted = ["args"]
    define_symbols_on_exit = "args"


class ClassDefHandler(DefiningConstructHandler):
    name = "ClassDef~S"
    children = {"name": 0, "bases": 1, "keywords": 2, "body": 3, "decorator_list": 4}
    targeted = []
    define_symbols_on_exit = "decorator_list"
    construct_name_field = "name"


child_frame_creators = [FuncDefHandler, LambdaHandler, ClassDefHandler]
