import ast
import ast_scope

from imperative_stitch.utils.ast_utils import ast_nodes_in_order


def get_name_and_scope_each(func_def):
    args = {x for x in ast_nodes_in_order(func_def.args)}
    annotation = ast_scope.annotate(func_def)
    nodes = [x for x in ast_nodes_in_order(func_def) if x in annotation]
    node_to_name_and_scope = {}
    name_and_scope_ordering = {}
    for i, node in enumerate(
        [x for x in nodes if x not in args] + [x for x in nodes if x in args]
    ):
        scope = annotation[node]
        if not isinstance(scope, ast_scope.scope.FunctionScope):
            continue
        name = scope.variables.node_to_symbol[node]
        node_to_name_and_scope[node] = (name, scope)
        if (name, scope) not in name_and_scope_ordering:
            name_and_scope_ordering[(name, scope)] = i
    return (
        node_to_name_and_scope,
        name_and_scope_ordering,
        annotation.function_scope_for(func_def),
    )


def canonicalize_variable_order(func_def, input_variables, output_variables):
    _, name_and_scope_ordering, scope = get_name_and_scope_each(func_def)
    var_order = lambda x: name_and_scope_ordering[(x, scope)]
    input_variables = sorted(input_variables, key=var_order)
    output_variables = sorted(output_variables, key=var_order)
    return input_variables, output_variables
