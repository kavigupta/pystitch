from .defining_statement_handler import DefiningStatementHandler


class ImportHandler(DefiningStatementHandler):
    name = "Import~S"
    children = {"names": 0}
    targeted = ["names"]
    define_symbols_on_exit = "names"


class ImportFromHandler(ImportHandler):
    name = "ImportFrom~S"
    children = {"module": 0, "names": 1}
