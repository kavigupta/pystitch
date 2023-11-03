import ast

import ast_scope

from imperative_stitch.utils.ast_utils import ast_nodes_in_order, name_field


def get_name_and_scope_each(func_def, metavariables, *, do_not_change_internal_args):
    args = set(ast_nodes_in_order(func_def.args))
    metavariable_call_nodes = {
        x for call in metavariables.all_calls for x in ast_nodes_in_order(call)
    }
    annotation = ast_scope.annotate(func_def)
    nodes = [x for x in ast_nodes_in_order(func_def) if x in annotation]
    node_to_name_and_scope = {}
    name_and_scope_ordering = {}
    name_and_scope_is_arg = set()
    for i, node in enumerate(
        [x for x in nodes if x not in (args | metavariable_call_nodes)]
        + [x for x in nodes if x in args]
        + [x for x in nodes if x in metavariable_call_nodes]
    ):
        scope = annotation[node]
        if not isinstance(scope, ast_scope.scope.FunctionScope):
            continue
        name = scope.variables.node_to_symbol[node]
        if isinstance(node, ast.arg) and scope.function_node != func_def:
            name_and_scope_is_arg.add((name, scope))
        if name in metavariables.names:
            continue
        node_to_name_and_scope[node] = (name, scope)
        if (name, scope) not in name_and_scope_ordering:
            name_and_scope_ordering[(name, scope)] = i
    if do_not_change_internal_args:
        node_to_name_and_scope = {
            k: v
            for k, v in node_to_name_and_scope.items()
            if v not in name_and_scope_is_arg
        }
        name_and_scope_ordering = {
            k: v
            for k, v in name_and_scope_ordering.items()
            if k not in name_and_scope_is_arg
        }
    return (
        node_to_name_and_scope,
        name_and_scope_ordering,
        annotation.function_scope_for(func_def),
    )


def canonicalize_variable_order(
    func_def,
    input_variables,
    output_variables,
    metavariables,
    *,
    do_not_change_internal_args,
):
    _, name_and_scope_ordering, scope = get_name_and_scope_each(
        func_def, metavariables, do_not_change_internal_args=do_not_change_internal_args
    )
    var_order = lambda x: name_and_scope_ordering[(x, scope)]
    input_variables = sorted(input_variables, key=var_order)
    output_variables = sorted(output_variables, key=var_order)
    return input_variables, output_variables


class NameChanger(ast.NodeTransformer):
    def __init__(self, node_to_new_name):
        self.node_to_new_name = node_to_new_name
        self.undos = []

    def generic_visit(self, node):
        if node not in self.node_to_new_name:
            return super().generic_visit(node)

        new_name = self.node_to_new_name[node]
        if name_field(node) is None:
            return super().generic_visit(node)

        if isinstance(node, ast.alias) and node.asname is None:
            self.undos.append(lambda: delattr(node, "asname"))
            setattr(node, "asname", new_name)
        else:
            old_name = getattr(node, name_field(node))
            self.undos.append(lambda: setattr(node, name_field(node), old_name))
            setattr(node, name_field(node), new_name)
        return super().generic_visit(node)


def canonicalize_names_in(func_def, metavariables, *, do_not_change_internal_args):
    node_to_name, name_and_scope_ordering, _ = get_name_and_scope_each(
        func_def, metavariables, do_not_change_internal_args=do_not_change_internal_args
    )
    scopes = [x[1] for x in name_and_scope_ordering]
    scopes = sorted(set(scopes), key=scopes.index)
    name_order_by_scope = {}
    total = 0
    for scope in scopes:
        names = [x[0] for x in name_and_scope_ordering if x[1] == scope]
        names = sorted(
            names, key=lambda x, scope=scope: name_and_scope_ordering[(x, scope)]
        )
        name_order_by_scope[scope] = {name: i + total for i, name in enumerate(names)}
        total += len(names)
    node_to_new_name = {}
    for node, (name, scope) in node_to_name.items():
        node_to_new_name[node] = f"__{name_order_by_scope[scope][name]}"
    name_changer = NameChanger(node_to_new_name)
    func_def = name_changer.visit(func_def)
    return func_def, name_changer.undos
