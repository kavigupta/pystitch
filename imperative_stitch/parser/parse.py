"""
There are three representations of a python program.

    1. actual python code, as a string. E.g., "x = 2"
    2. the ParsedAST representation we use
    3. s-expressions for stitch. E.g., "(Assign (list (Name &x:0 Store)) (Constant i2 None) None)"
"""

import ast
import base64

import ast_scope
from s_expression_parser import Pair, ParserConfig, Renderer, nil, parse

from imperative_stitch.utils.ast_utils import field_is_body, name_field, true_globals
from imperative_stitch.utils.recursion import recursionlimit

from .symbol import Symbol


def python_ast_to_parsed_ast(x, descoper, is_body=False):
    if is_body:
        assert isinstance(x, list), str(x)
        if not x:
            return []
        x = [python_ast_to_parsed_ast(x, descoper) for x in x]
        return ["/seq", *x]
    if isinstance(x, ast.AST):
        if not x._fields:
            return type(x)
        result = [type(x)]
        for f in x._fields:
            el = getattr(x, f)
            if x in descoper and f == name_field(x):
                assert isinstance(el, str), (x, f, el)
                result.append(Symbol(el, descoper[x]))
            else:
                result.append(
                    python_ast_to_parsed_ast(
                        el, descoper, is_body=field_is_body(type(x), f)
                    )
                )
        return result
    if x == []:
        return []
    if isinstance(x, list):
        return [list] + [python_ast_to_parsed_ast(x, descoper) for x in x]
    if x is None or x is Ellipsis or isinstance(x, (int, float, complex, str, bytes)):
        return x
    raise ValueError(f"Unsupported node {x}")


def to_python(x, is_body=False):
    if isinstance(x, list) and x and (x[0] == "/seq" or x[0] == "/subseq"):
        is_body = True
    if is_body:
        if x == []:
            return []
        if isinstance(x, list) and (x[0] == "/seq" or x[0] == "/subseq"):
            _, *rest = x
            return [to_python(x) for x in rest]
        return [to_python(x)]
    if isinstance(x, list):
        if x and callable(x[0]):
            if x[0] is list:
                return [to_python(x) for x in x[1:]]
            t, *x = x
            f = t._fields
            assert len(x) == len(f)
            x = t(*[to_python(x, field_is_body(t, f)) for x, f in zip(x, f)])
            x.lineno = 0
            return x
        return [to_python(x) for x in x]
    return x


def list_to_pair(x):
    x = x[:]
    result = nil
    while x:
        result = Pair(x.pop(), result)
    return result


def s_exp_to_pair(x):
    if x == []:
        return nil
    if isinstance(x, list):
        x = [s_exp_to_pair(x) for x in x]
        return list_to_pair(x)
    if isinstance(x, type):
        return x.__name__
    if x in {"/seq", "/subseq"}:
        return x
    if x is True or x is False or x is None or x is Ellipsis:
        return str(x)
    if isinstance(x, Symbol):
        return x.render()
    if isinstance(x, float):
        return f"f{x}"
    if isinstance(x, int):
        return f"i{x}"
    if isinstance(x, complex):
        return f"j{x}"
    if isinstance(x, str):
        # if all are renderable directly without whitespace, just use that
        if all(
            c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_."
            for c in x
        ):
            return "s_" + x
        return "s-" + base64.b64encode(str([ord(x) for x in x]).encode("ascii")).decode(
            "utf-8"
        )
    if isinstance(x, bytes):
        return "b" + base64.b64encode(x).decode("utf-8")
    raise ValueError(f"Unsupported: {type(x)}")


def pair_to_s_exp(x):
    if x == "list":
        return list
    if x is nil or x == "nil":
        return []
    if isinstance(x, Pair):
        if isinstance(x.car, str) and x.car.startswith("fn"):
            args = pair_to_s_exp(x.cdr)
            args = [
                [ast.Name, sym, [ast.Load]] if isinstance(sym, str) else sym
                for sym in args
            ]
            return [
                ast.Call,
                [ast.Name, x.car, [ast.Load]],
                [list, *args],
                [],
            ]
        return [pair_to_s_exp(x.car)] + pair_to_s_exp(x.cdr)
    assert isinstance(x, str), str(type(x))
    sym_x = Symbol.parse(x)
    if sym_x is not None:
        return sym_x.name
    if x.startswith("%"):
        return x
    if x.startswith("#") or x.startswith("?"):
        return ast.Name(id=x)

    if x == "Ellipsis":
        return Ellipsis
    if x in {"True", "False", "None"}:
        return ast.literal_eval(x)
    if x in {"/seq", "/subseq"}:
        return x
    if x == "/splice":
        return Splice
    if x.startswith("i"):
        return int(x[1:])
    if x.startswith("f"):
        return float(x[1:])
    if x.startswith("j"):
        return complex(x[1:])
    if x.startswith("s_"):
        return x[2:]
    if x.startswith("s-"):
        return "".join(
            chr(x)
            for x in ast.literal_eval(
                base64.b64decode(x[2:].encode("utf-8")).decode("ascii")
            )
        )
    if x.startswith("b"):
        return base64.b64decode(x[1:].encode("utf-8"))
    typ = getattr(ast, x)
    if typ._fields:
        return typ
    return typ()


class Splice:
    _fields = ["target"]

    def __new__(cls, target):
        return target


def parse_to_list_s_expression(code):
    with recursionlimit(max(1500, len(code))):
        code = ast.parse(code)
        code = python_ast_to_parsed_ast(code, create_descoper(code))
        return code


def python_to_s_exp(code, renderer_kwargs=None):
    if renderer_kwargs is None:
        renderer_kwargs = {}
    code = parse_to_list_s_expression(code)
    with recursionlimit(max(1500, len(code))):
        code = s_exp_to_pair(code)
        code = Renderer(**renderer_kwargs, nil_as_word=True).render(code)
        return code


def s_exp_parse(code):
    # pylint: disable=unbalanced-tuple-unpacking
    (code,) = parse(code, ParserConfig(prefix_symbols=[], dots_are_cons=False))
    return code


def s_exp_to_python(code):
    with recursionlimit(max(1500, len(code))):
        code = s_exp_parse(code)
        code = pair_to_s_exp(code)
        code = to_python(code)
        code = ast.unparse(code)
        return code


def create_descoper(code):
    globs = true_globals(code)
    annot = ast_scope.annotate(code)
    scopes = []
    results = {}
    for node in ast.walk(code):
        if node in annot:
            if node in globs:
                results[node] = None
                continue
            if annot[node] not in scopes:
                scopes.append(annot[node])
            results[node] = scopes.index(annot[node])
    return results
