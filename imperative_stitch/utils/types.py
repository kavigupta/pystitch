SEPARATOR = "~"


def get_dfa_state(sym):
    return sym.split(SEPARATOR)[1]


def clean_type(x):
    """
    Replace [] with __ in the type name
    """
    return x.replace("[", "_").replace("]", "_")


def unclean_type(x):
    """
    Replace __ with [] in the type name
    """
    if "_" not in x:
        return x
    assert x.count("_") == 2, x
    return x.replace("_", "[", 1).replace("_", "]", 1)
