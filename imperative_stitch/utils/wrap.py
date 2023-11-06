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
