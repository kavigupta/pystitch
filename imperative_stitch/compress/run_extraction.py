import ast

from imperative_stitch.analyze_program.antiunify.extract_at_multiple_sites import (
    antiunify_extractions,
)
from imperative_stitch.analyze_program.extract.extract import do_extract
from imperative_stitch.analyze_program.extract.extract_configuration import (
    ExtractConfiguration,
)
from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.data.parse_extract import parse_extract_pragma
from imperative_stitch.parser.parsed_ast import ParsedAST
from imperative_stitch.utils.wrap import (
    add_sentinel,
    split_by_sentinel_ast,
    unwrap_ast,
    wrap,
)


def add_pragmas_around_single_abstraction_call(parsed, abstr):
    """
    Add pragmas around a single abstraction call, selected as
    the first abstraction call in the parsed code.

    Args:
        parsed: ParsedAST
        abstr: dict[str, Abstraction]

    Returns:
        str, python code with pragmas added around the first abstraction call
    """
    ac = parsed.abstraction_calls()
    key = next(iter(ac))
    call = ac[key]
    ac[key] = abstr[call.tag].substitute_body(call.args, pragmas=True)
    parsed = parsed.replace_abstraction_calls(ac)
    parsed = parsed.abstraction_calls_to_bodies(abstr)
    return parsed.to_python()


def convert_output(abstractions, rewritten):
    """
    Convert the output of `run_julia_stitch` to actual python code
        using properly extracted python function abstractions.

    Args:
        abstractions: list[dict]
        rewritten: list[str]

    Returns:
        (abstraction: str, extracted: list[str])
        abstraction: str, the extracted python function
        extracted: list[str], the rewritten python code with the abstraction calls replaced

    Raises:
        NotApplicable: various errors related to the semantics not allowing for extraction
    """
    [abstr_dict] = abstractions
    abstr_dict = {
        **abstr_dict,
        "body": ParsedAST.parse_s_expression(abstr_dict["body"]),
    }
    abstr = dict(fn_1=Abstraction(name="fn_1", **abstr_dict))

    elements = {}
    unchanged = {}

    for i, code in enumerate(rewritten):
        parsed = ParsedAST.parse_s_expression(code)
        if not parsed.abstraction_calls():
            unchanged[i] = parsed.to_python()
            continue

        elements[i] = add_pragmas_around_single_abstraction_call(parsed, abstr)

    if not elements:
        raise ValueError("No abstraction calls found")

    abstraction, extracted = run_extraction(elements)
    extracted.update(unchanged)
    extracted = [extracted[i] for i in range(len(rewritten))]
    return abstraction, extracted


def run_extraction(elements):
    """
    Run extraction on the given elements.

    Args:
        elements: dict[int, str]

    Returns:
        (abstraction: str, extracted: dict[int, str])
        abstraction: str, the extracted python function
        extracted: dict[int, str], the rewritten python code with the abstraction calls replaced
    """
    keys = sorted(elements.keys())
    all_codes = "\n".join(add_sentinel(wrap(elements[k])) for k in keys)
    config = ExtractConfiguration(True)
    tree, sites = parse_extract_pragma(all_codes)
    extrs = [
        do_extract(site, tree, config=config, extract_name="__f0") for site in sites
    ]
    antiunify_extractions(extrs)
    post_extracteds = {ast.unparse(extr.func_def) for extr in extrs}
    [abstraction] = post_extracteds
    rewritten = split_by_sentinel_ast(tree)
    rewritten = [unwrap_ast(x) for x in rewritten]
    rewritten = {k: ast.unparse(v) for k, v in zip(keys, rewritten)}
    return abstraction, rewritten
