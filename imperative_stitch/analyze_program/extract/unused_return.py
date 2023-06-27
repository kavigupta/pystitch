import ast

from python_graphs import control_flow


def last_return_removable(func_def):
    """
    Can we remove the last return statement from the function definition?

    Args:
        func_def: AST, The function definition.

    Returns:
        True if the last return statement can be removed.
    """
    if not func_def.body:
        return False
    if not isinstance(func_def.body[-1], ast.Return):
        return False
    if func_def.body[-1].value is None:
        return True
    if len(func_def.body) == 1:
        return False
    module_def = ast.parse(ast.unparse(func_def))
    func_def = module_def.body[0]
    g = control_flow.get_control_flow_graph(module_def)
    [cfn] = [
        cfn
        for cfn in g.get_control_flow_nodes()
        if cfn.instruction.node == func_def.body[-1]
    ]
    if cfn.prev == set():
        return True
    return False


def remove_unnecessary_returns_one_step(func_def):
    """
    Remove the last return from the function definition if unnecessary.

    Returns:
        func_def: The function definition with the last return removed.
        changed: True if the function definition was changed.
    """
    if not last_return_removable(func_def):
        return func_def, False
    func_def.body.pop()
    if not func_def.body:
        func_def.body.append(ast.Pass())
    return func_def, True


def remove_unnecessary_returns(func_def):
    """
    Remove unnecessary returns from the function definition, if they appear
        at the end of the function.
    """
    while True:
        func_def, changed = remove_unnecessary_returns_one_step(func_def)
        if not changed:
            return func_def
