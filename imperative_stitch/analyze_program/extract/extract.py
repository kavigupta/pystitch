import ast
import copy

import ast_scope

from python_graphs import control_flow

from .errors import MultipleExits, NonInitializedInputs, NonInitializedOutputs
from .loop import replace_break_and_continue

from ..ssa.annotator import run_ssa
from ..ssa.ivm import DefinedIn, Phi


def extraction_entry_exit(pfcfg, nodes):
    entrys, exits = pfcfg.entry_and_exit_cfns(set(nodes))
    exits = [x for tag, x in exits if tag != "exception"]
    if not entrys:
        assert not exits
        return None, None
    [entry] = entrys
    if len(exits) > 1:
        raise MultipleExits
    if len(exits) == 0:
        # every path raises an exception, we don't have to do anything special
        exit = None
    else:
        [exit] = exits
    return entry, exit


def compute_ultimate_origins(origin_of):
    """
    For each variable list all the variables that are the ultimate origin of it.

    An ultimate origin is either the origin of a variable or, if the variable's origin
        is a Phi node, the ultimate origin of one of the variables that the Phi node
        depends on.
    """
    # TODO there's probably a faster way to do this but this is fast enough for now
    ultimate_origins = {}
    for var in origin_of:
        ultimate_origins[var] = set()
        seen = set()
        fringe = [var]
        while fringe:
            to_process = fringe.pop()
            if to_process in seen:
                continue
            seen.add(to_process)
            if isinstance(origin_of[to_process], Phi):
                fringe.extend(origin_of[to_process].parents)
            ultimate_origins[var].add(origin_of[to_process])
    return ultimate_origins


def variables_in_nodes(nodes, annotations):
    return {alias for x in nodes if x in annotations for alias in annotations[x]}


def is_origin_defined_in_node_set(origin, node_set):
    if isinstance(origin, DefinedIn):
        return node_set(origin.site)
    elif isinstance(origin, Phi):
        return node_set(origin.node)
    else:
        return node_set("<<function def>>")


def traces_an_origin_to_node_set(origins, node_set):
    return any(is_origin_defined_in_node_set(origin, node_set) for origin in origins)


def compute_input_variables(site, annotations, ultimate_origins, extracted_nodes):
    variables_in = variables_in_nodes(site.all_nodes, annotations)
    return sorted(
        [
            x[0]
            for x in variables_in
            if traces_an_origin_to_node_set(
                ultimate_origins[x], lambda x: x not in extracted_nodes
            )
        ]
    )


def compute_output_variables(
    pfcfg, site, annotations, ultimate_origins, extracted_nodes
):
    variables_out = variables_in_nodes(
        set(pfcfg.astn_order) - site.all_nodes, annotations
    )
    return sorted(
        {
            x[0]
            for x in variables_out
            if traces_an_origin_to_node_set(
                ultimate_origins[x], lambda x: x in extracted_nodes
            )
        }
    )


def all_initialized(lookup, vars, ultimate_origins):
    vars = [lookup[v] for v in vars]
    return all(all(x.initialized() for x in ultimate_origins[var]) for var in vars)


def create_target(variables, ctx):
    if len(variables) == 1:
        return ast.Name(id=variables[0], ctx=ctx)
    else:
        return ast.Tuple(
            elts=[ast.Name(id=x, ctx=ast.Load()) for x in variables], ctx=ctx
        )


def create_return_from_function(variables):
    if not variables:
        return ast.Return()
    return ast.Return(value=create_target(variables, ast.Load()))


def create_function_definition(extract_name, site, input_variables, output_variables):
    body = copy.deepcopy(site.statements())
    return_from_function = create_return_from_function(output_variables)
    body += [return_from_function]
    func_def = ast.FunctionDef(
        name=extract_name,
        args=ast.arguments(
            args=[ast.arg(name) for name in input_variables],
            kwonlyargs=[],
            posonlyargs=[],
            defaults=[],
        ),
        body=body,
        decorator_list=[],
    )
    func_def = ast.fix_missing_locations(func_def)
    _, _, func_def = replace_break_and_continue(func_def, return_from_function)
    func_def = remove_unnecessary_returns(func_def)
    return func_def


def last_return_removable(func_def):
    """
    Can we remove the last return statement from the function definition?
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


def create_function_call(extract_name, input_variables, output_variables, is_return):
    call = ast.Call(
        func=ast.Name(id=extract_name, ctx=ast.Load()),
        args=[ast.Name(id=x, ctx=ast.Load()) for x in input_variables],
        keywords=[],
    )
    if is_return:
        call = ast.Return(value=call)
    elif not output_variables:
        call = ast.Expr(value=call)
    else:
        call = ast.Assign(
            targets=[
                create_target(output_variables, ast.Store()),
            ],
            value=call,
            type_comment=None,
        )
    call = ast.fix_missing_locations(call)
    return call


def compute_extract_asts(scope_info, pfcfg, site, *, extract_name):
    """
    Returns the function definition and the function call for the extraction.
    """
    start, _, mapping, annotations = run_ssa(scope_info, pfcfg)
    extracted_nodes = {x for x in start if x.instruction.node in site.all_nodes}
    entry, exit = extraction_entry_exit(pfcfg, extracted_nodes)
    ultimate_origins = compute_ultimate_origins(mapping)
    input_variables = compute_input_variables(
        site, annotations, ultimate_origins, extracted_nodes
    )
    if exit is None or exit == "<return>":
        output_variables = []
    else:
        output_variables = compute_output_variables(
            pfcfg, site, annotations, ultimate_origins, extracted_nodes
        )

    if entry is not None and not all_initialized(
        start[entry], input_variables, ultimate_origins
    ):
        raise NonInitializedInputs
    if output_variables and not all_initialized(
        start[exit], output_variables, ultimate_origins
    ):
        raise NonInitializedOutputs
    func_def = create_function_definition(
        extract_name, site, input_variables, output_variables
    )
    call = create_function_call(
        extract_name, input_variables, output_variables, is_return=exit == "<return>"
    )
    return func_def, call, exit


def do_extract(site, tree, *, extract_name):
    """
    Mutate the AST to extract the code in `site` into a function named `extract_name`.

    Arguments
    ---------
    site: AST
        The site to extract.
    tree: AST
        The AST of the whole program.
    extract_name: str
        The name of the extracted function.

    Mutates the AST in place.

    Returns
    -------
    func_def: AST
        The function definition of the extracted function.
    undo: () -> None
        A function that undoes the extraction.
    """
    scope_info = ast_scope.annotate(tree)

    pfcfg = site.locate_entry_point(tree)
    func_def, call, exit = compute_extract_asts(
        scope_info, pfcfg, site, extract_name=extract_name
    )

    for calls in [call], [call, ast.Break()], [call, ast.Continue()]:
        success, undo = attempt_to_mutate(site, tree, calls, exit)
        if success:
            break
    else:
        raise AssertionError("Weird and unexpected control flow")

    return func_def, undo


def attempt_to_mutate(site, tree, calls, exit):
    """ """
    prev = site.containing_sequence[site.start : site.end]
    site.containing_sequence[site.start : site.end] = calls

    def undo():
        site.containing_sequence[site.start : site.start + len(calls)] = prev

    if exit is None:
        return True, undo
    new_pfcfg = site.locate_entry_point(tree)
    [call_cfn] = [
        cfn
        for cfn in new_pfcfg.next_cfns_of
        if cfn is not None and cfn.instruction.node == calls[0]
    ]
    call_exits = [
        x for tag, x in new_pfcfg.next_cfns_of[call_cfn] if tag != "exception"
    ]
    [exit_cfn] = call_exits
    if exit_cfn != exit and exit_cfn.instruction.node != exit.instruction.node:
        undo()
        return False, None
    return True, undo
