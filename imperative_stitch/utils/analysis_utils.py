import re

from typing import Dict, List

from ..parser import ParsedAST
from ..compress.abstraction import Abstraction
from imperative_stitch.utils.wrap import *


def strip_imports(program: str, strip_indented=True):
    output = []
    list_program = program.split("\n")
    for line in list_program:
        parsed = line.strip() if strip_indented else line
        if parsed.startswith("import ") or parsed.startswith("from "):
            continue
        output.append(line)
    return "\n".join(output)


def format_programs(inp: List[str], fn_name="def _main():"):
    """
    Strip imports, comments, docstrings, and code declaration punctation
    from programs returned by GPT-3.5 and GPT-4. Ignore programs that
    cannot be parsed by ast.parse.
    """
    code, imports = [], ""
    for program in inp:
        try:
            program = (
                program.removeprefix("```python")
                .removeprefix("```")
                .removesuffix("```")
            )
            wrapped = wrap(program)
        except Exception as e:
            print(f"failed to wrap program")
            print(e)
            continue
        start = wrapped.find(fn_name)
        imports += "\n" + wrapped[:start]
        code.append(strip_imports(program))
    return [ast.unparse(ast.parse(s)) for s in code], imports


# adapted from https://gist.github.com/phpdude/1ae6f19de213d66286c8183e9e3b9ec1
def strip_docstrings(program: str):
    parsed = ast.parse(program)

    for node in ast.walk(parsed):
        if not isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            continue
        if not len(node.body):
            continue
        if not isinstance(node.body[0], ast.Expr):
            continue
        if not hasattr(node.body[0], "value") or not isinstance(
            node.body[0].value, ast.Str
        ):
            continue
        node.body = node.body[1:]

        if not node.body:
            node.body.append(ast.Pass())

    return ast.unparse(parsed)


def sort_programs(programs, results):
    """
    Separate a set of responses to a task Q into correct and incorrect answers.
    """
    correct_programs, wrong_programs, idxs = [], [], []
    for i, program in enumerate(programs):
        result = results[i]
        result = [j if isinstance(j, bool) else False for j in result]
        target = program
        if all(result):
            correct_programs.append(target)
            idxs.append(i)
        else:
            wrong_programs.append(target)

    return correct_programs, wrong_programs, idxs


def unify_scope(program: str):
    """
    Rewrite all variables in the given program to have scope 0.
    """

    def helper(match_obj):
        target = match_obj.group(0)
        idx = target.find(":")
        return target[: idx + 1] + "0"

    return re.sub("&[a-zA-Z_][a-zA-Z0-9_]*:[0-9]*", helper, program)


def expand_all_abstractions(abstractions: List[Dict[str, str]]):
    """
    Remove nested abstractions from a set of Stitch abstractions.
    """
    output = {f"fn_{i+1}": v for i, v in enumerate(abstractions)}
    abstrs = {
        f"fn_{i+1}": Abstraction.of(name=f"fn_{i+1}", **v)
        for i, v in enumerate(abstractions)
    }
    for name, target in abstrs.items():
        while True:
            abstraction_calls = target.body.abstraction_calls()
            if not abstraction_calls:
                break
            target.body = target.body.abstraction_calls_to_bodies(abstrs)
            output[name]["body"] = target.body.to_s_exp()
    return [output[f"fn_{i+1}"] for i in range(len(output))]


def remove_unused_abstractions(programs: List[str], abstractions: List[Dict[str, str]]):
    """
    Given a program corpus and a set of abstractions, identify abstractions
    that are not used within the corpus. Rewrite the corpus to exclude
    unused abstractions.
    """
    used_abstractions = set()
    for program in programs:
        ast_program = ParsedAST.parse_s_expression(program)
        abstraction_calls = ast_program.abstraction_calls()
        for abstr in abstraction_calls.values():
            used_abstractions.add(abstr.tag)

    abstraction_set = {}
    expanded_abstractions = expand_all_abstractions(abstractions)
    output_abstractions = []
    for i, abstr in enumerate(expanded_abstractions):
        if f"fn_{i+1}" in used_abstractions:
            abstraction_set[f"fn_{i+1}"] = f"fn_{len(abstraction_set) + 1}"
            output_abstractions.append(abstr)

    rewritten_programs = []
    for program in programs:
        ast_program = ParsedAST.parse_s_expression(program)
        handle_to_abstractions = ast_program.abstraction_calls()
        for abstr in handle_to_abstractions.values():
            abstr.tag = abstraction_set[abstr.tag]
        rewritten_programs.append(
            ast_program.replace_abstraction_calls(handle_to_abstractions).to_s_exp()
        )

    return rewritten_programs, output_abstractions
