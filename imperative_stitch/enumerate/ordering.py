from typing import List

from ..parser.parsed_ast import ParsedAST, AbstractionCallAST


def abstraction_calls_ordered(ast: ParsedAST, nested=False) -> List[str]:
    """
    Return a list of all the metavariables, symbol variables, and choice variables in
        the order they appear in the body.
    """
    result = []
    seen = set()

    if not nested:
        abstraction_calls = ast.abstraction_calls()
        new_abst_calls = {
            id: AbstractionCallAST(tag=a.tag, args=[], handle=id)
            for id, a in abstraction_calls.items()
        }
        ast = ast.replace_abstraction_calls(new_abst_calls)

    def collect_variable(node):
        if isinstance(node, AbstractionCallAST):
            if node.handle not in seen:
                result.append(node)
                seen.add(node.handle)
        return node

    ast.map(collect_variable)
    return result


def order_replacements_map(ast, handle_to_replacement):
    return [handle_to_replacement[a.handle] for a in abstraction_calls_ordered(ast)]


def map_ordered_replacements(ast, args):
    abstraction_calls = abstraction_calls_ordered(ast)
    assert len(abstraction_calls) == len(args)
    handle_to_replacement = {
        abstraction_calls[i].handle: args[i] for i in range(len(args))
    }
    return handle_to_replacement
