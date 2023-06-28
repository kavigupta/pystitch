import ast
import ast_scope

from imperative_stitch.utils.ast_utils import ast_nodes_in_order, name_field


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


class NameChanger(ast.NodeTransformer):
    def __init__(self, node_to_new_name):
        self.node_to_new_name = node_to_new_name

    def generic_visit(self, node):
        if node in self.node_to_new_name:
            setattr(node, name_field(node), self.node_to_new_name[node])
        return super().generic_visit(node)


def canonicalize_names_in(func_def):
    node_to_name, name_and_scope_ordering, _ = get_name_and_scope_each(func_def)
    scopes = {x[1] for x in name_and_scope_ordering}
    name_order_by_scope = {}
    for scope in scopes:
        names = [x[0] for x in name_and_scope_ordering if x[1] == scope]
        names = sorted(names, key=lambda x: name_and_scope_ordering[(x, scope)])
        name_order_by_scope[scope] = {name: i for i, name in enumerate(names)}
    node_to_new_name = {}
    for node, (name, scope) in node_to_name.items():
        node_to_new_name[node] = f"__{name_order_by_scope[scope][name]}"
    func_def = NameChanger(node_to_new_name).visit(func_def)
    return func_def
