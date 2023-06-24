import ast
import base64

import attr
import ast_scope
from imperative_stitch.utils.ast_utils import field_is_body

from imperative_stitch.utils.recursion import recursionlimit
from s_expression_parser import Pair, nil, Renderer, parse, ParserConfig


@attr.s(hash=True)
class Symbol:
    name = attr.ib()
    scope = attr.ib()

    @classmethod
    def parse(cls, x):
        assert x.startswith("&")
        name, scope = x[1:].split(":")
        return cls(name, scope)

    def render(self):
        return f"&{self.name}:{self.scope}"


def is_the_symbol(node, f):
    x = type(node).__name__
    if x == "Name":
        return f == "id"
    if x == "FunctionDef" or x == "AsyncFunctionDef":
        return f == "name"
    if x == "ClassDef":
        return f == "name"
    if x == "arg":
        return f == "arg"
    if x == "ExceptHandler":
        return f == "name" and node.name is not None
    if x == "alias":
        if node.asname is None:
            return f == "name"
        return f == "asname"
    raise ValueError(f"Unsupported: {node}")


def to_list_s_expr(x, descoper, is_body=False):
    if is_body:
        assert isinstance(x, list), str(x)
        if not x:
            return []
        x = [to_list_s_expr(x, descoper) for x in x]
        result = x.pop()
        while x:
            result = ["semi", x.pop(), result]
        return result
    if isinstance(x, ast.AST):
        if not x._fields:
            return type(x)
        result = [type(x)]
        for f in x._fields:
            el = getattr(x, f)
            if x in descoper and is_the_symbol(x, f):
                assert isinstance(el, str)
                result.append(Symbol(el, descoper[x]))
            else:
                result.append(
                    to_list_s_expr(el, descoper, is_body=field_is_body(type(x), f))
                )
        return result
    if x == []:
        return []
    if isinstance(x, list):
        return [list] + [to_list_s_expr(x, descoper) for x in x]
    if x is None or x is Ellipsis or isinstance(x, (int, float, complex, str, bytes)):
        return x
    raise ValueError(f"Unsupported node {x}")


def to_python(x, is_body=False):
    if is_body:
        if x == []:
            return []
        elif isinstance(x, list) and x[0] == "semi":
            _, first, second = x
            return to_python(first, True) + to_python(second, True)
        else:
            return [to_python(x)]
    if isinstance(x, list):
        if x and isinstance(x[0], type):
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
    if x in {"semi"}:
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
        return [pair_to_s_exp(x.car), *pair_to_s_exp(x.cdr)]
    assert isinstance(x, str), str(type(x))
    if x.startswith("&"):
        return Symbol.parse(x).name
    if x == "Ellipsis":
        return Ellipsis
    if x in {"True", "False", "None"}:
        return ast.literal_eval(x)
    if x in {"semi"}:
        return x
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


def python_to_s_exp(code, renderer_kwargs=dict()):
    with recursionlimit(max(1500, len(code))):
        code = ast.parse(code)
        code = to_list_s_expr(code, descoper(code))
        code = s_exp_to_pair(code)
        code = Renderer(**renderer_kwargs, nil_as_word=True).render(code)
        return code


def s_exp_to_python(code):
    with recursionlimit(max(1500, len(code))):
        (code,) = parse(code, ParserConfig(prefix_symbols=[], dots_are_cons=False))
        code = pair_to_s_exp(code)
        code = to_python(code)
        code = ast.unparse(code)
        return code


def descoper(code):
    annot = ast_scope.annotate(code)
    scopes = []
    results = {}
    for node in ast.walk(code):
        if node in annot:
            if annot[node] not in scopes:
                scopes.append(annot[node])
            results[node] = scopes.index(annot[node])
    return results
