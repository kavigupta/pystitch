import ast
import ast_scope


def compute_variable_order(func_def):
    annotation = ast_scope.annotate(func_def)
    nodes = [
        x
        for x in ast.walk(func_def)
        if not isinstance(x, ast.arg)
        and x in annotation
        and isinstance(annotation[x], ast_scope.scope.FunctionScope)
        and annotation[x].function_node == func_def
    ]
    if not nodes:
        return []
    to_name = annotation[nodes[0]].variables.node_to_symbol
    nodes = [to_name[x] for x in nodes]
    order = {}
    for i, x in enumerate(nodes):
        if x not in order:
            order[x] = i
    return order


def canonicalize_variable_order(func_def, input_variables, output_variables):
    variable_order = compute_variable_order(func_def)
    input_variables = sorted(input_variables, key=lambda x: variable_order[x])
    output_variables = sorted(output_variables, key=lambda x: variable_order[x])
    return input_variables, output_variables
