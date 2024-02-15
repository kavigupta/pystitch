import ast
import json

from frozendict import frozendict

TRANSITIONS = frozendict(
    {
        "M": {ast.Module: {"body": "seqS", "type_ignores": "X"}},
        "S": {
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef): {
                "body": "seqS",
                "decorator_list": "listE",
                "bases": "listE",
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
            (ast.Import, ast.ImportFrom): {"names": "alias"},
            (ast.Global, ast.Nonlocal): {"names": "names"},
            ast.Expr: {"value": "E"},
        },
        "E": {
            (ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare): {
                "op": "O",
                "ops": "O",
                "comparators": "listE",
                "values": "listE",
                all: "E",
            },
            ast.NamedExpr: {"value": "E", "target": "L"},
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
            ): {
                "ctx": "X",
                "elts": "listE_starrable",
                "keys": "listE",
                "values": "listE",
                all: "E",
            },
            (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp): {
                "generators": "C",
                all: "E",
            },
            ast.Call: {
                "keywords": "K",
                "args": "listE_starrable",
                all: "E",
            },
            ast.JoinedStr: {"values": "listF"},
            (ast.Constant, ast.Name, ast.AnnAssign): {all: "X"},
            (ast.Attribute, ast.Subscript, ast.Starred): {
                "value": "E",
                "slice": "SliceRoot",
                all: "X",
            },
        },
        "SliceRoot": {
            "_slice_content": {all: "E"},
            "_slice_slice": {all: "Slice"},
            "_slice_tuple": {all: "SliceTuple"},
        },
        "SliceTuple": {
            ast.Tuple: {"elts": "listSliceRoot", "ctx": "X"},
        },
        "listSliceRoot": {"list": "SliceRoot"},
        "StarredRoot": {
            "_starred_content": {all: "E"},
            "_starred_starred": {all: "Starred"},
        },
        "Starred": {ast.Starred: {"value": "E"}},
        "Slice": {
            ast.Slice: {"lower": "E", "upper": "E", "step": "E"},
        },
        "As": {
            ast.arguments: {
                ("kw_defaults", "defaults"): "listE",
                all: "A",
            }
        },
        "A": {
            ast.arg: {"annotation": "E"},
        },
        "X": {all: {all: "X"}},
        "F": {
            ast.FormattedValue: {"value": "E", "format_spec": "F"},
            ast.Constant: {all: "F"},
            ast.JoinedStr: {"values": "listF"},
        },
        "C": {
            ast.comprehension: {
                "target": "L",
                "iter": "E",
                "ifs": "listE",
                "is_async": "X",
            }
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
            ast.Name: {all: "X"},
            ast.Tuple: {all: "L"},
            ast.List: {all: "L"},
            ast.Subscript: {"value": "E", "slice": "SliceRoot"},
            ast.Attribute: {"value": "E", "attr": "X"},
            "list": "L",
            ast.Starred: {all: "L"},
            "_starred_content": {all: "L"},
            "_starred_starred": {all: "Starred"},
        },
        "seqS": {},
        "listE": {"list": "E"},
        "listE_starrable": {"list": "StarredRoot"},
        "O": {"list": "O"},
        "alias": {"list": "alias", ast.alias: {all: "X"}},
        "names": {"list": "X"},
        "listF": {"list": "F"},
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


def compute_transition(transitions, state, typ, fields):
    transition = transitions[state]
    transition = compute_match(transition, typ, default=False)
    if transition is False:
        return None
    return [compute_match(transition, field, default="X") for field in fields]


def compute_types_each(t, state):
    if isinstance(t, list):
        for x in t:
            yield from compute_types_each(x, state)
        return
    if isinstance(t, ast.AST):
        print(state, ast.dump(t))
        yield t, state
        fields = t._fields
        states = compute_transition(TRANSITIONS, state, type(t), fields)
        assert states is not None, (t, state)
        for f, new_state in zip(fields, states):
            yield from compute_types_each(getattr(t, f), new_state)


def flatten_types(ts):
    if isinstance(ts, (list, tuple)):
        for x in ts:
            yield from flatten_types(x)
        return
    if ts is all:
        return
    if isinstance(ts, type):
        yield ts.__name__
        return
    assert isinstance(ts, str), ts
    yield ts


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

    extras = [
        "_slice_content",
        "_slice_slice",
        "_slice_tuple",
        "_starred_content",
        "_starred_starred",
    ]

    result = {}
    for state in transitions:
        result[state] = {}
        for tag in all_tags:
            t = getattr(ast, tag)
            out = compute_transition(transitions, state, t, t._fields)
            if out is not None:
                result[state][tag] = out
        for tag in extras:
            out = compute_transition(transitions, state, tag, [None])
            if out is not None:
                result[state][tag] = out

        missing = (
            set(flatten_types(list(transitions[state])))
            - set(result[state])
            - {"list", "/seq", "/splice"}
        )
        if missing:
            raise RuntimeError(f"in state {state}: missing {missing}")

        result[state]["list"] = [transitions[state].get("list", state)]
    for state in transitions:
        result[state]["/seq"] = ["X"]
        result[state]["/splice"] = ["X"]
    result["seqS"]["/seq"] = ["S"]
    result["S"]["/splice"] = ["seqS"]
    return result


if __name__ == "__main__":
    print(json.dumps(export_dfa(), indent=2))
