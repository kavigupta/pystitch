import ast
import copy
from dataclasses import dataclass
from typing import Callable, Dict

import ast_scope

from imperative_stitch.analyze_program.extract.errors import (
    BothYieldsAndReturns,
    MultipleExits,
)
from imperative_stitch.analyze_program.extract.metavariable import (
    MetaVariables,
    extract_metavariables,
)
from imperative_stitch.analyze_program.extract.pre_and_post_process import preprocess
from imperative_stitch.utils.ast_utils import name_field

from ..ssa.annotator import run_ssa
from ..ssa.ivm import Gamma
from .generator import is_function_generator
from .input_output_variables import compute_variables, traces_an_origin_to_node_set
from .loop import replace_break_and_continue
from .stable_variable_order import canonicalize_names_in, canonicalize_variable_order
from .unused_return import remove_unnecessary_returns


@dataclass
class ExtractedCode:
    """
    Represents the code that has been extracted from the site.
    """

    func_def: ast.AST
    call: ast.AST
    metavariables: MetaVariables
    undo: Callable[[], None]


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
    extract_name, site, input_variables, output_variables, metavariables, ensure_global
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
    ensure_global: list[ast.AST]
        The variables that should be global in this function.

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
    scope_info = ast_scope.annotate(func_def)
    make_global = [
        getattr(astn, name_field(astn))
        for astn in set(scope_info) & set(ensure_global)
        if scope_info[astn] is not scope_info.global_scope
    ]
    if make_global:
        func_def.body = [ast.Global(names=sorted(set(make_global)))] + func_def.body
    func_def = ast.fix_missing_locations(func_def)
    _, _, func_def, undo = replace_break_and_continue(func_def, return_from_function)
    func_def = remove_unnecessary_returns(func_def)
    return func_def, undo


def create_function_call(
    extract_name,
    input_variables,
    output_variables,
    metavariables,
    is_return,
    is_generator,
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
    is_generator: bool
        True if the extracted site is a generator

    Returns
    -------
    call: [AST]
        The function call. Can be multiple statements.
    """
    if is_generator and output_variables:
        raise BothYieldsAndReturns
    call = ast.Call(
        func=ast.Name(id=extract_name, ctx=ast.Load()),
        args=[ast.Name(id=x, ctx=ast.Load()) for x in input_variables]
        + metavariables.parameters,
        keywords=[],
    )
    if is_generator:
        call = ast.Expr(ast.YieldFrom(value=call))
        if is_return:
            call = [call, ast.Return()]
    elif is_return:
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
    if not isinstance(call, list):
        call = [call]
    call = [ast.fix_missing_locations(stmt) for stmt in call]
    return call


def compute_extract_asts(tree, site, *, config, extract_name, undos):
    """
    Returns the function definition and the function call for the extraction.

    Arguments
    ---------
    site: ExtractionSite
        The extraction site.
    config: ExtractConfiguration
        The configuration for the extraction.
    extract_name: str
        The name of the extracted function.
    undos:
        a list of functions that undoes the extraction, will be added to

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
    metavariables:
        A Metavariables object representing the metavariables.
    """
    undo_preprocess = preprocess(tree)
    scope_info = ast_scope.annotate(tree)
    undos += [undo_preprocess]
    undo_sentinel = site.inject_sentinel()
    undos += [undo_sentinel]
    pfcfg = site.locate_entry_point(tree)
    start, _, _, annotations = run_ssa(scope_info, pfcfg)
    extracted_nodes = {x for x in start if x.instruction.node in site.all_nodes}
    _, exit, _ = pfcfg.extraction_entry_exit(extracted_nodes)

    global_variables = [
        x for x in scope_info if scope_info[x] is scope_info.global_scope
    ]
    vars = compute_variables(site, scope_info, pfcfg)
    vars.raise_if_needed()

    metavariables = extract_metavariables(scope_info, site, annotations, vars)

    undo_metavariables = metavariables.act(pfcfg.function_astn)
    undos += [undo_metavariables]

    scope_info = ast_scope.annotate(tree)

    pfcfg = site.locate_entry_point(tree)

    vars = compute_variables(
        site,
        scope_info,
        pfcfg,
        error_on_closed=True,
        guarantee_outputs_of=vars.output_vars_ssa,
    )
    vars.raise_if_needed()

    undos.remove(undo_sentinel)
    undo_sentinel()

    func_def, undo_replace = create_function_definition(
        extract_name,
        site,
        vars.input_vars_without_ssa,
        vars.output_vars_without_ssa,
        metavariables,
        global_variables,
    )

    input_variables, output_variables = canonicalize_variable_order(
        func_def,
        vars.input_vars_without_ssa,
        vars.output_vars_without_ssa,
        metavariables,
        do_not_change_internal_args=config.do_not_change_internal_args,
    )
    undo_replace()

    func_def, undo_replace = create_function_definition(
        extract_name,
        site,
        input_variables,
        output_variables,
        metavariables,
        global_variables,
    )
    undos += [undo_replace]
    func_def, undo_canonicalize = canonicalize_names_in(
        func_def,
        metavariables,
        do_not_change_internal_args=config.do_not_change_internal_args,
    )
    undos += undo_canonicalize
    call = create_function_call(
        extract_name,
        input_variables,
        output_variables,
        metavariables,
        is_return=exit == "<return>",
        is_generator=is_function_generator(func_def),
    )
    undos.remove(undo_preprocess)
    undo_preprocess()
    return func_def, call, exit, metavariables


def do_extract(site, tree, *, config, extract_name):
    """
    Mutate the AST to extract the code in `site` into a function named `extract_name`.

    Arguments
    ---------
    site: AST
        The site to extract.
    tree: AST
        The AST of the whole program.
    config: ExtractConfiguration
        The configuration for the extraction.
    extract_name: str
        The name of the extracted function.

    Mutates the AST in place.

    Returns
    -------
    ExtractedCode
        The extracted code, including the function definition, the function call, and
            a function that undoes the extraction.
    """
    undos = []

    def full_undo():
        for un in undos[::-1]:
            un()

    try:
        func_def, call, metavariables = _do_extract(
            site, tree, config=config, extract_name=extract_name, undos=undos
        )
    except:
        full_undo()
        raise

    return ExtractedCode(func_def, call, metavariables, full_undo)


def _do_extract(site, tree, *, config, extract_name, undos):
    func_def, call, exit, metavariables = compute_extract_asts(
        tree, site, config=config, extract_name=extract_name, undos=undos
    )

    for calls in [*call], [*call, ast.Break()], [*call, ast.Continue()]:
        success, undo_mutate = attempt_to_mutate(site, tree, calls, exit)
        if success:
            undos += [undo_mutate]
            break
    else:
        raise AssertionError("Weird and unexpected control flow")

    return func_def, call, metavariables


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
    for call in calls[::-1]:
        call_cfns = [
            cfn
            for cfn in new_pfcfg.next_cfns_of
            if cfn is not None and cfn.instruction.node == call
        ]
        if call_cfns:
            [call_cfn] = call_cfns
            break
    else:
        assert False, "should have found a call cfn"
    call_exits = [
        x for tag, x in new_pfcfg.next_cfns_of[call_cfn] if tag != "exception"
    ]
    # This should not be necessary, it results from a bug in the control flow graph
    if len(call_exits) > 1:
        undo()
        raise MultipleExits
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
