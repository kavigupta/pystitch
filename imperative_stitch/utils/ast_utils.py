import ast


def field_is_body(t, f):
    assert isinstance(t, type)
    if t == ast.IfExp:
        return False  # not body of statements
    if t == ast.Lambda:
        return False  # not body of statements
    return f in {"body", "orelse", "finalbody"}
