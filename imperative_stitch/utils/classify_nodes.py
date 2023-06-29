import ast

transitions = {
    "M": {ast.Module: {"body": "S", "type_ignores": "X"}},
    "S": {
        (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef): {
            "body": "S",
            "decorator_list": "E",
            "bases": "E",
            "name": "X",
            "args": "As",
            "returns": "X",
            "type_comment": "X",
            "keywords": "K",
        },
        ast.Return: {"value": "E"},
        ast.Delete: {"targets": "X"},
        (ast.Assign, ast.AugAssign, ast.AnnAssign): {
            "value": "E",
            "targets": "X",
            "target": "X",
            "type_comment": "X",
            "op": "X",
            "annotation": "X",
            "simple": "X",
        },
        (ast.For, ast.AsyncFor, ast.While, ast.If, ast.With, ast.Try): {
            "iter": "E",
            "test": "E",
            "body": "S",
            "orelse": "S",
            "finalbody": "S",
            "items": "W",
            "handlers": "EH",
            "target": "X",
            "type_comment": "X",
        },
        #         ast.Match: {"subject": "E", "cases": "C"},
        ast.Raise: {all: "E"},
        ast.Assert: {all: "E"},
        (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal): {all: "X"},
        ast.Expr: {"value": "E"},
    },
    "E": {
        (ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare): {
            "op": "X",
            "ops": "X",
            all: "E",
        },
        ast.NamedExpr: {"value": "E", "target": "X"},
        ast.Lambda: {"args": "As", "body": "E"},
        (
            ast.IfExp,
            ast.Dict,
            ast.Set,
            ast.List,
            ast.Tuple,
            ast.Await,
            ast.Yield,
            ast.YieldFrom,
        ): {"ctx": "X", all: "E"},
        (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp): {
            "generators": "C",
            all: "E",
        },
        ast.Call: {
            "keywords": "K",
            all: "E",
        },
        ast.JoinedStr: {"values": "F"},
        (ast.Constant, ast.Name): {all: "X"},
        (ast.Attribute, ast.Subscript, ast.Starred): {"value": "E", all: "X"},
    },
    "As": {
        ast.arguments: {
            ("kw_defaults", "defaults"): "E",
            all: "X",
        }
    },
    "X": {all: {all: "X"}},
    "F": {
        ast.FormattedValue: {"value": "E", all: "X"},
        ast.Constant: {all: "X"},
    },
    "C": {ast.comprehension: {"target": "X", "iter": "E", "ifs": "E", "is_async": "X"}},
    "K": {ast.keyword: {"value": "E", "arg": "X"}},
    "EH": {
        ast.ExceptHandler: {
            "type": "X",
            "name": "X",
            "body": "S",
        }
    },
    "W": {
        ast.withitem: {
            "context_expr": "E",
            "optional_vars": "X",
        }
    },
}


def compute_match(transition, key):
    for k, v in transition.items():
        if k is all:
            return v
        if not isinstance(k, tuple):
            k = (k,)
        if key in k:
            return v
    raise RuntimeError(f"could not find {key}")


def compute_transition(state, typ, field):
    transition = transitions[state]
    transition = compute_match(transition, typ)
    transition = compute_match(transition, field)
    return transition


def compute_types_each(t, state):
    if isinstance(t, list):
        for x in t:
            yield from compute_types_each(x, state)
        return
    if isinstance(t, ast.AST):
        yield t, state
        for f in t._fields:
            yield from compute_types_each(
                getattr(t, f), compute_transition(state, type(t), f)
            )
