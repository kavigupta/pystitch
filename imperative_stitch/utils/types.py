import neurosym as ns

SEPARATOR = "~"
non_sequence_prefixes = ("fn_", "var-")


def get_dfa_state(sym):
    return sym.split(SEPARATOR)[1]


def is_sequence(type_name, head_symbol):
    return ns.python_ast_tools.is_sequence(
        type_name, head_symbol, non_sequence_prefixes
    )
