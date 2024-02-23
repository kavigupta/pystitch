import ast
import json

from frozendict import frozendict

# exclude these tags from the dfa. these are all python 3.10+ features,
# and for consistency across python versions, we exclude them. We can
# add them back in later if we want to support them.
EXCLUDED_TAGS = [
    # match
    "Match",
    "MatchAs",
    "MatchMapping",
    "MatchSequence",
    "MatchValue",
    "MatchClass",
    "MatchOr",
    "MatchSingleton",
    "MatchStar",
    "match_case",
    "pattern",
    # trystar
    "TryStar",
]

TRANSITIONS = frozendict(
    {
        "M": {ast.Module: {"body": "seqS", "type_ignores": "TI"}},
        "S": {
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef): {
                "body": "seqS",
                "decorator_list": "listE",
                "bases": "listE",
                "name": "Name",
                "args": "As",
                "returns": "TA",
                "type_comment": "TC",
                "keywords": "K",
            },
            ast.Return: {"value": "E"},
            ast.Delete: {"targets": "L"},
            (ast.Assign, ast.AugAssign, ast.AnnAssign): {
                "value": "E",
                "targets": "L",
                "target": "L",
                "type_comment": "TC",
                "op": "O",
                "annotation": "TA",
                "simple": "bool",
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
                "type_comment": "TC",
            },
            #         ast.Match: {"subject": "E", "cases": "C"},
            ast.Raise: {all: "E"},
            ast.Assert: {all: "E"},
            (ast.Import, ast.ImportFrom): {
                "names": "alias",
                "module": "NullableNameStr",
                "level": "int",
            },
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
                "ctx": "Ctx",
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
            ast.Constant: {"value": "Const", "kind": "ConstKind"},
            ast.Name: {"id": "Name", "ctx": "Ctx"},
            (ast.Attribute, ast.Subscript, ast.Starred): {
                "value": "E",
                "attr": "NameStr",
                "slice": "SliceRoot",
                "ctx": "Ctx",
            },
        },
        "SliceRoot": {
            "_slice_content": {all: "E"},
            "_slice_slice": {all: "Slice"},
            "_slice_tuple": {all: "SliceTuple"},
        },
        "SliceTuple": {
            ast.Tuple: {"elts": "listSliceRoot", "ctx": "Ctx"},
        },
        "listSliceRoot": {"list": "SliceRoot"},
        "StarredRoot": {
            "_starred_content": {all: "E"},
            "_starred_starred": {all: "Starred"},
        },
        "Starred": {ast.Starred: {"value": "E", "ctx": "Ctx"}},
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
            ast.arg: {"annotation": "TA", "arg": "Name", "type_comment": "TC"},
        },
        "F": {
            ast.FormattedValue: {"value": "E", "format_spec": "F", "conversion": "int"},
            ast.Constant: {all: "F"},
            ast.JoinedStr: {"values": "listF"},
        },
        "C": {
            ast.comprehension: {
                "target": "L",
                "iter": "E",
                "ifs": "listE",
                "is_async": "bool",
            }
        },
        "K": {ast.keyword: {"value": "E", "arg": "NullableNameStr"}},
        "EH": {
            ast.ExceptHandler: {
                "type": "E",
                "name": "NullableName",
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
            ast.Name: {
                "id": "Name",
                "ctx": "Ctx",
            },
            ast.Tuple: {"elts": "L", "ctx": "Ctx"},
            ast.List: {"elts": "L", "ctx": "Ctx"},
            ast.Subscript: {"value": "E", "slice": "SliceRoot", "ctx": "Ctx"},
            ast.Attribute: {"value": "E", "attr": "NameStr", "ctx": "Ctx"},
            "list": "L",
            ast.Starred: {all: "L"},
            "_starred_content": {all: "L"},
            "_starred_starred": {all: "Starred"},
        },
        "seqS": {},
        "listE": {"list": "E"},
        "listE_starrable": {"list": "StarredRoot"},
        "O": {"list": "O"},
        "alias": {
            "list": "alias",
            ast.alias: {
                "name": "NameStr",
                "asname": "NullableNameStr",
            },
        },
        "names": {"list": "NameStr"},
        "listF": {"list": "F"},
        "TA": {all: {all: "TA"}},
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
    raise RuntimeError(f"could not find {key} in {transition}")


def compute_transition(transitions, state, typ, fields):
    transition = transitions[state]
    transition = compute_match(transition, typ, default=False)
    if transition is False:
        return None
    return [compute_match(transition, field) for field in fields]


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
        and x not in EXCLUDED_TAGS
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
