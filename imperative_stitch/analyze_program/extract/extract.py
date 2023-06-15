import ast

import ast_scope

from .errors import (
    NonInitializedInputs,
    NonInitializedOutputs,
    UnexpectedControlFlowException,
)

from ..ssa.annotator import run_ssa
from ..ssa.ivm import DefinedIn, Phi


def extraction_entry_exit(pfcfg, nodes):
    entrys, exits = pfcfg.entry_and_exit_cfns(set(nodes))
    [entry] = entrys
    if len(exits) > 1:
        raise NotImplementedError("Multiple exits not supported")
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
            else:
                ultimate_origins[var].add(origin_of[to_process])
    return ultimate_origins


def variables_in_nodes(nodes, annotations):
    return {alias for x in nodes if x in annotations for alias in annotations[x]}


def is_defined_in_node_set(ultimate_origin_of_var, extracted_nodes):
    for origin in ultimate_origin_of_var:
        if isinstance(origin, DefinedIn):
            if origin.site in extracted_nodes:
                return True
    return False


def compute_input_variables(site, annotations, ultimate_origins, extracted_nodes):
    variables_in = variables_in_nodes(site.all_nodes, annotations)
    return sorted(
        [
            x[0]
            for x in variables_in
            if not is_defined_in_node_set(ultimate_origins[x], extracted_nodes)
        ]
    )


def compute_output_variables(
    pfcfg, site, annotations, ultimate_origins, extracted_nodes
):
    variables_out = variables_in_nodes(
        set(pfcfg.astn_order) - site.all_nodes, annotations
    )
    return sorted(
        [
            x[0]
            for x in variables_out
            if is_defined_in_node_set(ultimate_origins[x], extracted_nodes)
        ]
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


def create_return_nodes(variables):
    if not variables:
        return []
    return [ast.Return(value=create_target(variables, ast.Load()))]


def create_function_definition(extract_name, site, input_variables, output_variables):
    body = site.statements()[:]
    body += create_return_nodes(output_variables)
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
    return func_def


def create_function_call(extract_name, input_variables, output_variables, is_return):
    call = ast.Call(
        func=ast.Name(id=extract_name, ctx=ast.Load()),
        args=[ast.Name(id=x, ctx=ast.Load()) for x in input_variables],
        keywords=[],
    )
    if is_return:
        call = ast.Return(value=call)
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

    if not all_initialized(start[entry], input_variables, ultimate_origins):
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
    prev = site.node.body[site.start : site.end]
    site.node.body[site.start : site.end] = [call]

    def undo():
        site.node.body[site.start : site.start + 1] = prev

    if exit is not None:
        new_pfcfg = site.locate_entry_point(tree)
        [call_cfn] = [
            cfn for cfn in new_pfcfg.next_cfns_of if cfn.instruction.node == call
        ]
        print(call_cfn)
        print(new_pfcfg.next_cfns_of)
        [exit_cfn] = new_pfcfg.next_cfns_of[call_cfn]
        if exit_cfn != exit and exit_cfn.instruction.node != exit.instruction.node:
            undo()
            raise UnexpectedControlFlowException

    return func_def, undo
