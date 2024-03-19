from ..handler import Handler


class ChildFrameCreatorHandler(Handler):
    def __init__(
        self, mask, valid_symbols, config, *, fields, field_name, field_for_child_frame
    ):
        self.original_valid_symbols = valid_symbols
        super().__init__(mask, set(valid_symbols), config)
        self.name = None
        self.fields = fields
        self.field_name = field_name
        self.field_for_child_frame = field_for_child_frame

    def on_enter(self):
        pass

    def on_exit(self):
        if self.name is not None:
            assert self.name is not None
            self.original_valid_symbols.add(self.name)

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        if self.field_name is not None and position == self.fields[self.field_name]:
            self.name = symbol
            self.valid_symbols.add(symbol)
        if (
            self.field_for_child_frame is not None
            and position == self.fields[self.field_for_child_frame]
        ):
            return self.target_child(symbol)
        return super().on_child_enter(position, symbol)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        if (
            self.field_for_child_frame is not None
            and position == self.fields[self.field_for_child_frame]
        ):
            self.valid_symbols |= child.defined_symbols

    def is_defining(self, position: int) -> bool:
        if self.field_name is not None:
            if position == self.fields[self.field_name]:
                return True
        if self.field_for_child_frame is not None:
            if position == self.fields[self.field_for_child_frame]:
                return True
        return False


class FuncDefHandler(ChildFrameCreatorHandler):
    name = "FunctionDef~S"

    def __init__(self, mask, valid_symbols, config):
        super().__init__(
            mask,
            valid_symbols,
            config,
            fields={"name": 0, "args": 1, "body": 2},
            field_name="name",
            field_for_child_frame="args",
        )


class LambdaHandler(ChildFrameCreatorHandler):
    name = "Lambda~E"

    def __init__(self, mask, valid_symbols, config):
        super().__init__(
            mask,
            valid_symbols,
            config,
            fields={"args": 0, "body": 1},
            field_name=None,
            field_for_child_frame="args",
        )


class ClassDefHandler(ChildFrameCreatorHandler):
    name = "ClassDef~S"

    def __init__(self, mask, valid_symbols, config):
        super().__init__(
            mask,
            valid_symbols,
            config,
            fields={"name": 0},
            field_name="name",
            field_for_child_frame=None,
        )


child_frame_creators = [FuncDefHandler, LambdaHandler, ClassDefHandler]
