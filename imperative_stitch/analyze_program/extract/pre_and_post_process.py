import ast


class ReplaceBareExcept(ast.NodeTransformer):
    """
    Replaces bare except clauses with except Exception.
    """

    def __init__(self):
        self.names = []

    def visit_ExceptHandler(self, node):
        name = ast.Name(id="Exception", ctx=ast.Load())
        self.names.append(name)
        if node.type is None:
            node.type = name
        return node


class UndoReplaceBareExcept(ast.NodeTransformer):
    """
    Undoes the replacement of bare except clauses with except Exception.
    """

    def __init__(self, names):
        self.names = names

    def visit_ExceptHandler(self, node):
        if node.type in self.names:
            node.type = None
        return node


def preprocess(function_astn):
    """
    Preprocesses the function ASTN to make it easier to extract from.

    Specifically does
        - converts bare except clauses to except Exception
    """

    replace = ReplaceBareExcept()
    replace.visit(function_astn)

    return lambda: postprocess(replace.names, function_astn)


def postprocess(names, function_astn):
    """
    Postprocess the function ASTN to undo the preprocessing.
    """
    undo = UndoReplaceBareExcept(names)
    undo.visit(function_astn)
