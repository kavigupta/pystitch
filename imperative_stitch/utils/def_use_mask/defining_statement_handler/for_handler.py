from .defining_statement_handler import DefiningStatementHandler


class ForHandler(DefiningStatementHandler):
    name = "For~S"
    children = {"target": 0, "iter": 1, "body": 2, "orelse": 3}
    targeted = ["target"]
    define_symbols_on_exit = "iter"
