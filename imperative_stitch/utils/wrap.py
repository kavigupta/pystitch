import ast


def wrap(code):
    body = ast.parse(code).body
    imports = []
    for node in body:
        if isinstance(node, ast.Import):
            imports.append(node)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node)
        else:
            break
    body = body[len(imports) :]
    return ast.unparse(
        ast.fix_missing_locations(
            ast.Module(
                body=[
                    *imports,
                    ast.FunctionDef(
                        name="_main",
                        args=[],
                        body=body,
                        decorator_list=[],
                    ),
                    ast.Expr(
                        ast.Call(
                            func=ast.Name(id="_main", ctx=ast.Load()),
                            args=[],
                            keywords=[],
                        )
                    ),
                ],
                type_ignores=[],
            )
        )
    )
