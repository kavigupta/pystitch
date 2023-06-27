import ast
import copy

import ast_scope

from python_graphs import control_flow

from imperative_stitch.analyze_program.extract.input_output_variables import (
    compute_input_variables,
    compute_output_variables,
)

from .errors import NonInitializedInputs, NonInitializedOutputs
from .loop import replace_break_and_continue
from .stable_variable_order import canonicalize_names_in, canonicalize_variable_order
from ..ssa.annotator import run_ssa
from ..ssa.ivm import compute_ultimate_origins


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
    """
    Create the function call for the extracted function. Can be either a return
        statement (if the extracted site returns a value), an assignment (if the
        extracted site has output variables), or an expression (if the extracted
        site has no output variables and does not return a value).

    Arguments
    ---------
    extract_name: str
        The name of the extracted function to create.
    input_variables: list[str]
        The input variables of the extracted function.
    output_variables: list[str]
        The output variables of the extracted function.
    is_return: bool
        True if the extracted site returns a value.

    Returns
    -------
    call: AST
        The function call.
    """
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

    Arguments
    ---------
    scope_info: ScopeInfo
        The scope information of the program.
    pfcfg: PerFunctionCFG
        The per-function control flow graph for the relevant function
    site: ExtractionSite
        The extraction site.
    extract_name: str
        The name of the extracted function.

    Returns
    -------
    func_def: AST
        The function definition of the extracted function.
    call: AST
        The function call of the extracted function.
    exit:
        The exit node of the extraction site.
    """
    start, _, mapping, annotations = run_ssa(scope_info, pfcfg)
    extracted_nodes = {x for x in start if x.instruction.node in site.all_nodes}
    entry, exit = pfcfg.extraction_entry_exit(extracted_nodes)
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
    input_variables, output_variables = canonicalize_variable_order(
        func_def,
        input_variables,
        output_variables,
    )
    func_def = create_function_definition(
        extract_name, site, input_variables, output_variables
    )
    func_def = canonicalize_names_in(func_def)
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
    """
    Attempt to mutate the AST to replace the extraction site with the given calls code.

    Checks that the exit of the extraction site is the same as the exit of the calls code.

    Arguments
    ---------
    site: ExtractionSite
        The extraction site.
    tree: AST
        The AST of the whole program.
    calls: list[AST]
        The code to replace the extraction site with.
    exit: ControlFlowNode
        The exit of the extraction site.

    Returns
    -------
    success: bool
        True if the mutation was successful, i.e., the exit of the extraction site is the
            same as the exit of the calls code.
    undo: () -> None
        A function that undoes the mutation, or None if the mutation was unsuccessful (in
            which case the AST is not mutated)
    """
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
