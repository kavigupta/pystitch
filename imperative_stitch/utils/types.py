SEPARATOR = "~"


def get_dfa_state(sym):
    return sym.split(SEPARATOR)[1]
