"""
Takes code like

    def f(xs, ys):
        zs = []
        for x, y in zip(xs, ys):
            __start_extract__
            x2y2 = x ** 2 + y ** 2
            r = x2y2 ** {__metavariable__, __m1, 0.5}
            z = x + r
            __end_extract__
            zs.append(z)
        return zs

and parses it as if the __start_extract__, __end_extract__, and __metavariable__
were not there, returning an AST of the code and the ExtractionSite objects.
"""

import ast
from collections import defaultdict

from imperative_stitch.analyze_program.extract import ExtractionSite
from imperative_stitch.utils.ast_utils import field_is_body


class RemoveExprMetavariablesPragmas(ast.NodeTransformer):
    def __init__(self, metavariable_pragma):
        self.metavariable_pragma = metavariable_pragma
        self.metavariables = {}

    def visit_Set(self, node):
        node = super().generic_visit(node)
        if len(node.elts) != 3:
            return node
        pragma, name, value = node.elts
        if not isinstance(pragma, ast.Name):
            return node
        if pragma.id != self.metavariable_pragma:
            return node
        assert isinstance(name, ast.Name)
        assert name.id not in self.metavariables
        self.metavariables[name.id] = value
        return value


class RemoveStartEndPragmas(ast.NodeTransformer):
    """
    Removes pragmas from the AST, and collect the extraction site
    """

    def __init__(self, start_pragma, end_pragma, metavariable_pragma):
        self.start_pragma = start_pragma
        self.end_pragma = end_pragma
        self.metavariable_pragma = metavariable_pragma
        self.sites = []

    def visit(self, node):
        for f in node._fields:
            setattr(node, f, self._visit_field(node, f))
        node = super().generic_visit(node)
        return node

    def _visit_field(self, node, field):
        if not field_is_body(type(node), field):
            return getattr(node, field)
        body = getattr(node, field)
        assert isinstance(body, list)
        pragma_idxs = get_pragmas(body, self.start_pragma, self.end_pragma)
        if not pragma_idxs[self.start_pragma]:
            return body
        [start_index] = pragma_idxs[self.start_pragma]
        [end_index] = pragma_idxs[self.end_pragma]
        assert start_index < end_index
        metavariables = RemoveExprMetavariablesPragmas(self.metavariable_pragma)
        for i in range(start_index + 1, end_index):
            body[i] = metavariables.visit(body[i])
        # subtract 1 from end_index because the end pragma is not part of the body
        self.sites.append(
            ExtractionSite(
                node, field, start_index, end_index - 1, metavariables.metavariables
            )
        )
        return (
            body[:start_index]
            + body[start_index + 1 : end_index]
            + body[end_index + 1 :]
        )


def get_pragmas(body, *pragmas):
    """
    Returns the indices of the pragmas in the body.
    """
    pragma_idxs = defaultdict(list)
    for i, node in enumerate(body):
        if isinstance(node, ast.Expr):
            node = node.value
        if isinstance(node, ast.Name) and node.id in pragmas:
            pragma_idxs[node.id].append(i)
    return pragma_idxs


def parse_extract_pragma(
    code,
    start_pragma="__start_extract__",
    end_pragma="__end_extract__",
    metavariable_pragma="__metavariable__",
):
    """
    Parses code with pragmas, and returns the AST and the extraction sites.
    """
    astn = ast.parse(code)
    rmp = RemoveStartEndPragmas(start_pragma, end_pragma, metavariable_pragma)
    astn = rmp.visit(astn)
    return astn, rmp.sites
