import neurosym as ns

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


def is_sequence_type(x):
    x = ns.parse_type(x)
    if isinstance(x, ns.ListType):
        return True
    if not isinstance(x, ns.AtomicType):
        return False
    return x.name == "seqS"


def is_sequence_symbol(x):
    return x in ["/seq", "/subseq", "list", "/choiceseq"]


def is_sequence(type_name, head_symbol):
    if head_symbol.startswith("fn_") or head_symbol.startswith("var-"):
        return False
    seq_type = is_sequence_type(type_name)
    seq_symbol = is_sequence_symbol(head_symbol)
    assert seq_type == seq_symbol or type_name in ns.pruned_python_dfa_states, (
        seq_type,
        seq_symbol,
        type_name,
        head_symbol,
    )
    return seq_type or seq_symbol
