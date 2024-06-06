import ast


def add_sentinel(code):
    """
    Add a __sentinel__ to the front of the code.
    """

    return "__sentinel__\n" + code


def split_by_sentinel_ast(code):
    """
    Split the tree by __sentinel__.
    """
    assert isinstance(code, ast.Module)
    body = code.body
    assert isinstance(body, list)
    result = []
    for line in body:
        if isinstance(line, ast.Expr):
            if isinstance(line.value, ast.Name) and line.value.id == "__sentinel__":
                result.append([])
                continue
        result[-1].append(line)
    return [ast.Module(body=lines, type_ignores=[]) for lines in result]
