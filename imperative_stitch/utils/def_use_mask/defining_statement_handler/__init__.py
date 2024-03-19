from .assign_handler import AssignHandler
from .functiondef_handler import FuncDefHandler, LambdaHandler
from .import_handler import ImportHandler
from .chained_definitions_handler import chained_definition_handlers


def defining_statement_handlers():
    return {
        x.name: x
        for x in [
            AssignHandler,
            ImportHandler,
            FuncDefHandler,
            LambdaHandler,
            *chained_definition_handlers,
        ]
    }
