import ast


class StreamOfChildren(ast.NodeVisitor):
    def __init__(self):
        self.stream = []

    def visit(self, node):
        self.stream.append(node)
        super().visit(node)


def get_node_order(astn):
    stream = StreamOfChildren()
    stream.visit(astn)
    return {node: i for i, node in enumerate(stream.stream)}


def name_vars(original_symbol_of, var_order):
    """
    Name variables in the order they are given.

    Args:
        original_symbol_of: A mapping from variable id to its original symbol.
        var_order: A list of variable id.

    Returns:
        A mapping from variable id to (symbol, index).

    E.g., {1 : "x", 2 : "y", 3 : "x", 4 : "y"}, [1, 2, 3, 4] -> {1 : ("x", 1), 2 : ("y", 1), 3 : ("x", 2), 4 : ("y", 2)}
    """
    counts_each = {}
    result = {}
    for var in var_order:
        if var in result:
            continue
        sym = original_symbol_of[var]
        counts_each[sym] = counts_each.get(sym, 0) + 1
        result[var] = sym, counts_each[sym]
    return result
