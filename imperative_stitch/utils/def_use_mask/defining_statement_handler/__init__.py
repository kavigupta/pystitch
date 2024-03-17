from .assign_handler import AssignHandler
from .functiondef_handler import FuncDefHandler
from .import_handler import ImportHandler


def defining_statement_handlers():
    return {x.name: x for x in [AssignHandler, ImportHandler, FuncDefHandler]}
