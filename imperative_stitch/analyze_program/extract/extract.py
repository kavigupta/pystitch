import ast
import copy

import ast_scope

from imperative_stitch.analyze_program.extract.metavariable import (
    extract_metavariables,
)


from .input_output_variables import (
    compute_variables,
)
from .unused_return import remove_unnecessary_returns

from .errors import (
    ClosureOverVariableModifiedInExtractedCode,
    NonInitializedInputs,
    NonInitializedOutputs,
)
from .loop import replace_break_and_continue
from .stable_variable_order import canonicalize_names_in, canonicalize_variable_order
from ..ssa.annotator import run_ssa
from ..ssa.ivm import Gamma, compute_ultimate_origins


def invalid_closure_over_variable_modified_in_non_extracted_code(
    site, annotations, extracted_nodes, mapping
):
    """
    Returns True if there is a closure over a variable that is modified in non-extracted

    Arguments
    ---------
    site: ExtractionSite
        The extraction site.
    annotations: dict[AST, set[str]]
        A mapping from node to the set of variables defined in the node.
    extracted_nodes: set[AST]
        The set of nodes in the extraction site.

    Returns
    -------
    bool
        Whether there is a Gamma node that is a closure over a variable that is modified
    """
    origins = [
        mapping[k] for x in site.all_nodes if x in annotations for k in annotations[x]
    ]
    origins = [
        mapping[down] for x in origins if isinstance(x, Gamma) for down in x.downstreams
    ]
    return traces_an_origin_to_node_set(origins, lambda x: x not in extracted_nodes)


def create_target(variables, ctx):
    """
    Create a target from a list of variables.

    Arguments
    ---------
    variables: list[str]
        The variables to create a target from.
    ctx: AST
        The context of the target, either ast.Load() or ast.Store().

    Returns
    -------
    target: AST
        The target. Either an ast.Name or an ast.Tuple.
    """
    if len(variables) == 1:
        return ast.Name(id=variables[0], ctx=ctx)
    else:
        return ast.Tuple(elts=[ast.Name(id=x, ctx=ctx) for x in variables], ctx=ctx)


def create_return_from_function(variables):
    """
    Create a return statement from a list of variables.

    Arguments
    ---------
    variables: list[str]
        The variables to create a return statement from.

    Returns
    -------
    return: AST
        The return statement.
    """
    if not variables:
        return ast.Return()
    return ast.Return(value=create_target(variables, ast.Load()))


def create_function_definition(
    extract_name, site, input_variables, output_variables, metavariables
):
    """
    Create a function definition for the extracted function.

    Arguments
    ---------
    extract_name: str
        The name of the extracted function.
    site: ExtractionSite
        The extraction site.
    input_variables: list[str]
        The input variables of the extracted function.
    output_variables: list[str]
        The output variables of the extracted function.
    metavariables: MetaVariables
        The metavariables of the extracted function.

    Returns
    -------
    func_def: AST
        The function definition.
    """
    body = copy.copy(site.statements())
    return_from_function = create_return_from_function(output_variables)
    body += [return_from_function]
    func_def = ast.FunctionDef(
        name=extract_name,
        args=ast.arguments(
            args=[ast.arg(name) for name in input_variables + metavariables.names],
            kwonlyargs=[],
            posonlyargs=[],
            defaults=[],
        ),
        body=body,
        decorator_list=[],
    )
    func_def = ast.fix_missing_locations(func_def)
    _, _, func_def, undo = replace_break_and_continue(func_def, return_from_function)
    func_def = remove_unnecessary_returns(func_def)
    return func_def, undo


def create_function_call(
    extract_name, input_variables, output_variables, metavariables, is_return
):
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
        args=[ast.Name(id=x, ctx=ast.Load()) for x in input_variables]
        + metavariables.parameters,
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


def compute_extract_asts(tree, scope_info, site, *, extract_name):
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
    undos:
        A list of functions that undoes the extraction.
    """
    pfcfg = site.locate_entry_point(tree)

    start, _, _, annotations = run_ssa(scope_info, pfcfg)
    extracted_nodes = {x for x in start if x.instruction.node in site.all_nodes}
    _, exit = pfcfg.extraction_entry_exit(extracted_nodes)

    vars = compute_variables(site, scope_info, pfcfg)

    vars.raise_if_needed([])

    metavariables = extract_metavariables(scope_info, site, annotations, vars)

    undos = []

    undo_metavariables = metavariables.act(pfcfg.function_astn)
    undos += [undo_metavariables]

    pfcfg = site.locate_entry_point(tree)

    vars = compute_variables(site, scope_info, pfcfg, error_on_closed=True)
    vars.raise_if_needed(undos)

    func_def, undo_replace = create_function_definition(
        extract_name,
        site,
        vars.input_vars_without_ssa,
        vars.output_vars_without_ssa,
        metavariables,
    )
    undos += [undo_replace]

    input_variables, output_variables = canonicalize_variable_order(
        func_def,
        vars.input_vars_without_ssa,
        vars.output_vars_without_ssa,
        metavariables.names,
    )
    func_def, undo_replace = create_function_definition(
        extract_name, site, input_variables, output_variables, metavariables
    )
    undos += [undo_replace]
    func_def, undo_canonicalize = canonicalize_names_in(func_def, metavariables.names)
    undos += undo_canonicalize
    call = create_function_call(
        extract_name,
        input_variables,
        output_variables,
        metavariables,
        is_return=exit == "<return>",
    )
    return func_def, call, exit, undos


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

    func_def, call, exit, undos = compute_extract_asts(
        tree, scope_info, site, extract_name=extract_name
    )

    for calls in [call], [call, ast.Break()], [call, ast.Continue()]:
        success, undo = attempt_to_mutate(site, tree, calls, exit)
        if success:
            break
    else:
        for undo in undos[::-1]:
            undo()
        raise AssertionError("Weird and unexpected control flow")

    def full_undo():
        undo()
        for un in undos[::-1]:
            un()

    return func_def, full_undo


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
    if not same(exit_cfn, exit):
        undo()
        return False, None
    return True, undo


def same(a, b):
    if isinstance(a, str) and not isinstance(b, str):
        return False
    if isinstance(b, str) and not isinstance(a, str):
        return False
    assert type(a) == type(b)
    if isinstance(a, str):
        return a == b
    return a.instruction.node == b.instruction.node
