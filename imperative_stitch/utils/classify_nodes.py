import ast
import json

from frozendict import frozendict

TRANSITIONS = frozendict(
    {
        "M": {ast.Module: {"body": "seqS", "type_ignores": "X"}},
        "S": {
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef): {
                "body": "seqS",
                "decorator_list": "E",
                "bases": "E",
                "name": "X",
                "args": "As",
                "returns": "E",
                "type_comment": "X",
                "keywords": "K",
            },
            ast.Return: {"value": "E"},
            ast.Delete: {"targets": "L"},
            (ast.Assign, ast.AugAssign, ast.AnnAssign): {
                "value": "E",
                "targets": "L",
                "target": "L",
                "type_comment": "X",
                "op": "X",
                "annotation": "E",
                "simple": "X",
            },
            (
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.If,
                ast.With,
                ast.AsyncWith,
                ast.Try,
            ): {
                "iter": "E",
                "test": "E",
                "body": "seqS",
                "orelse": "seqS",
                "finalbody": "seqS",
                "items": "W",
                "handlers": "EH",
                "target": "L",
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
            (ast.Constant, ast.Name, ast.AnnAssign): {all: "X"},
            (ast.Attribute, ast.Subscript, ast.Starred): {
                "value": "E",
                "slice": "E",
                all: "X",
            },
            ast.Slice: {"lower": "E", "upper": "E", "step": "E"},
        },
        "As": {
            ast.arguments: {
                ("kw_defaults", "defaults"): "E",
                all: "A",
            }
        },
        "A": {
            ast.arg: {"annotation": "E"},
        },
        "X": {all: {all: "X"}},
        "F": {
            ast.FormattedValue: {"value": "E", all: "X"},
            ast.Constant: {all: "X"},
        },
        "C": {
            ast.comprehension: {"target": "L", "iter": "E", "ifs": "E", "is_async": "X"}
        },
        "K": {ast.keyword: {"value": "E", "arg": "X"}},
        "EH": {
            ast.ExceptHandler: {
                "type": "E",
                "name": "X",
                "body": "seqS",
            }
        },
        "W": {
            ast.withitem: {
                "context_expr": "E",
                "optional_vars": "L",
            }
        },
        "L": {
            ast.Tuple: {all: "L"},
            ast.Subscript: {"value": "E", "slice": "E"},
            ast.Attribute: {"value": "E", "attr": "X"},
        },
        "seqS": {}
    }
)


def compute_match(transition, key, default=None):
    for k, v in transition.items():
        if k is all:
            return v
        if not isinstance(k, tuple):
            k = (k,)
        if key in k:
            return v
    if default is not None:
        return default
    raise RuntimeError(f"could not find {key}")


def compute_transition(transitions, state, typ, field):
    transition = transitions[state]
    transition = compute_match(transition, typ, default={})
    transition = compute_match(transition, field, default="X")
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
                getattr(t, f), compute_transition(TRANSITIONS, state, type(t), f)
            )


def export_dfa(transitions=TRANSITIONS):
    """
    Takes a transition dictionary of the form above and converts
    it to a dict[state, dict[tag, list[state]]]
    """
    all_tags = [
        x
        for x in dir(ast)
        if isinstance(getattr(ast, x), type) and issubclass(getattr(ast, x), ast.AST)
    ]

    result = {}
    for state in transitions:
        result[state] = {}
        for tag in all_tags:
            result[state][tag] = []
            t = getattr(ast, tag)
            for f in t._fields:
                result[state][tag].append(compute_transition(transitions, state, t, f))
    for state in transitions:
        result[state]["list"] = [state]
    for state in transitions:
        result[state]["/seq"] = ["X"]
        result[state]["/splice"] = ["X"]
    result["seqS"]["/seq"] = ["S"]
    result["S"]["/splice"] = ["seqS"]
    return result


if __name__ == "__main__":
    print(json.dumps(export_dfa(), indent=2))
