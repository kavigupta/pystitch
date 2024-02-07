import ast


def wrap_ast(code, fn_name="_main"):
    body = code.body
    imports = []
    for node in body:
        if isinstance(node, ast.Import):
            imports.append(node)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node)
        else:
            break
    body = body[len(imports) :]
    if not body:
        body = [ast.Pass()]
    return ast.Module(
        body=[
            *imports,
            ast.FunctionDef(
                name=fn_name,
                args=ast.arguments(
                    posonlyargs=[],
                    args=[],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[],
                ),
                body=body,
                decorator_list=[],
            ),
            ast.Expr(
                ast.Call(
                    func=ast.Name(id=fn_name, ctx=ast.Load()),
                    args=[],
                    keywords=[],
                )
            ),
        ],
        type_ignores=[],
    )


def wrap(code, fn_name="_main"):
    return ast.unparse(ast.fix_missing_locations(wrap_ast(ast.parse(code), fn_name)))


def clean_for_unwrap(body):
    if body and isinstance(body[-1], ast.Pass):
        body = body[:-1]
    if body and isinstance(body[-1], ast.Return):
        body[-1] = ast.Expr(value=body[-1].value)
    return body


def unwrap_ast(code):
    """
    Unwrap the code.
    """
    assert isinstance(code, ast.Module)
    body = code.body
    assert isinstance(body, list)
    assert len(body) >= 2
    imports = []
    for node in body:
        if isinstance(node, ast.Import):
            imports.append(node)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node)
        else:
            break
    body = body[len(imports) :]
    assert len(body) == 2
    assert isinstance(body[0], ast.FunctionDef)
    output = imports + clean_for_unwrap(body[0].body)
    assert ast.unparse(body[1]) == f"{body[0].name}()", (
        ast.unparse(body[1]),
        body[0].name,
    )
    return ast.Module(body=output, type_ignores=[])


def unwrap(code):
    return ast.unparse(unwrap_ast(ast.parse(code)))
