def abstraction_calls_to_stubs(program, abstractions):
    """
    Replace all abstraction calls with stubs. Does so via a double iteration.
        Possibly faster to use a linearization of the set of stubs.
    """
    result = program
    while True:
        abstraction_calls = result.abstraction_calls()
        if not abstraction_calls:
            return result
        replacement = {}
        for handle, node in abstraction_calls.items():
            if (set(node.abstraction_calls()) - {handle}) == set():
                replacement[handle] = abstractions[node.tag].create_stub(node.args)
        result = result.replace_abstraction_calls(replacement)


def abstraction_calls_to_bodies(program, abstractions, *, pragmas=False):
    """
    Replace all abstraction calls with their bodies.
    """
    return program.map_abstraction_calls(
        lambda call: abstractions[call.tag].substitute_body(call.args, pragmas=pragmas)
    )


def abstraction_calls_to_bodies_recursively(program, abstractions, *, pragmas=False):
    """
    Replace all abstraction calls with their bodies, recursively.
    """
    result = program
    while True:
        result = abstraction_calls_to_bodies(result, abstractions, pragmas=pragmas)
        if not result.abstraction_calls():
            return result
