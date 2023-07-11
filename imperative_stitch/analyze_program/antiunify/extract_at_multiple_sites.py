import ast


def reconfigure_parameter(parameter, vars, vars_all):
    """
    Mutate the parameter to increase the number of variables.

    E.g., if parameter is lambda x, z: x + z, and vars is [a, b], and
        vars_all is [a, b, c], then the result is lambda x, __u1, z: x + z.

    Args:
        parameter (ast.Lambda): The parameter to reconfigure.
        vars (list[str]): The current variables used to call the parameter.
        vars_all (list[str]): The eventual variables used to call the parameter.
    """
    arg_names = [x.arg for x in parameter.args.args]
    assert len(arg_names) == len(vars)
    i = 0

    def unused():
        nonlocal i
        i += 1
        return f"__u{i}"

    new_args_names = []
    for v in vars_all:
        if v in vars:
            new_args_names.append(arg_names[vars.index(v)])
        else:
            new_args_names.append(unused())
    parameter.args.args = [ast.arg(name) for name in new_args_names]


def antiunify_all_metavariables_across_extractions(extrs):
    """
    Antiunify all metavariables across all extractions. Once this is done,
        all metavariables will have the same number of passed variables.

    Args:
        extrs (list[Extraction]): The extractions to antiunify.
    """
    all_metavariable_names = sorted(
        {name for extr in extrs for name in extr.metavariables.names}
    )
    for metavariable_name in all_metavariable_names:
        antiunify_metavariable_across_extractions(extrs, metavariable_name)

    codes = set(ast.unparse(extr.func_def) for extr in extrs)
    if len(codes) != 1:
        for code in codes:
            print(code)
        raise RuntimeError("not all results are the same")


def antiunify_metavariable_across_extractions(extrs, metavariable_name):
    """
    Antiunify the given metavariable across all extractions. Once this is done,
        the metavariable will have the same number of passed variables.

    Args:
        extrs (list[Extraction]): The extractions to antiunify.
        metavariable_name (str): The name of the metavariable to antiunify.
    """
    metavariables = [
        extr.metavariables.replacements_for_name(metavariable_name)[0] for extr in extrs
    ]
    parameters = [
        extr.metavariables.parameter_for_name(metavariable_name) for extr in extrs
    ]
    vars_each = []
    for meta in metavariables:
        assert meta.call.func.id == metavariable_name
        vars_each.append([arg.id for arg in meta.call.args])
    vars_all = sorted({var for vars in vars_each for var in vars})
    for extr, parameter, meta, vars in zip(extrs, parameters, metavariables, vars_each):
        for meta in extr.metavariables.replacements_for_name(metavariable_name):
            meta.call.args = [ast.Name(var, ast.Load()) for var in vars_all]
        reconfigure_parameter(parameter, vars, vars_all)
