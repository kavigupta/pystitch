from .defining_statement_handler import DefiningStatementHandler, Handler


class AssignHandler(DefiningStatementHandler):
    name = "Assign~S"
    children = {"target": 0, "value": 1, "type_comment": 2}
    targeted = ["target"]
    define_symbols_on_exit = "type_comment"
