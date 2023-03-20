import ast
import base64

from s_expression_parser import Pair, nil, Renderer, parse, ParserConfig


def field_is_body(t, f):
    assert isinstance(t, type)
    if t == ast.IfExp:
        return False # not body of statements
    if t == ast.Lambda:
        return False # not body of statements
    return f in {"body", "orelse", "finalbody"}


def to_list_s_expr(x, is_body=False):
    if is_body:
        assert isinstance(x, list), str(x)
        if not x:
            return ["empty"]
        x = [to_list_s_expr(x) for x in x]
        result = x.pop()
        while x:
            result = ["semi", x.pop(), result]
        return result
    if isinstance(x, ast.AST):
        return [type(x)] + [
            to_list_s_expr(getattr(x, f), field_is_body(type(x), f)) for f in x._fields
        ]
    if isinstance(x, list):
        return [to_list_s_expr(x) for x in x]
    if x is None or isinstance(x, (str, int, float)):
        return x
    raise ValueError(f"Unsupported node {x}")


def to_python(x, is_body=False):
    if is_body:
        if x == ["empty"]:
            return []
        elif isinstance(x, list) and x[0] == "semi":
            _, first, second = x
            return to_python(first, True) + to_python(second, True)
        else:
            return [to_python(x)]
    if isinstance(x, list):
        if x and isinstance(x[0], type):
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
    if isinstance(x, list):
        x = [s_exp_to_pair(x) for x in x]
        return list_to_pair(x)
    if isinstance(x, type):
        return x.__name__
    if x in {"semi", "empty"}:
        return x
    if x is True or x is False or x is None:
        return str(x)
    if isinstance(x, float):
        return f"f{x}"
    if isinstance(x, int):
        return f"i{x}"
    if isinstance(x, str):
        return "s" + base64.b64encode(x.encode("utf-8")).decode("utf-8")
    raise ValueError(f"Unsupported: {type(x)}")


def pair_to_s_exp(x):
    if x is nil:
        return []
    if isinstance(x, Pair):
        return [pair_to_s_exp(x.car), *pair_to_s_exp(x.cdr)]
    assert isinstance(x, str), str(type(x))
    if x in {"True", "False", "None"}:
        return ast.literal_eval(x)
    if x in {"semi", "empty"}:
        return x
    if x.startswith("i"):
        return int(x[1:])
    if x.startswith("f"):
        return float(x[1:])
    if x.startswith("s"):
        return base64.b64decode(x[1:].encode("utf-8")).decode("utf-8")
    return getattr(ast, x)


def python_to_s_exp(code, renderer_kwargs=dict()):
    code = ast.parse(code)
    code = to_list_s_expr(code)
    code = s_exp_to_pair(code)
    code = Renderer(**renderer_kwargs).render(code)
    return code


def s_exp_to_python(code):
    (code,) = parse(code, ParserConfig(prefix_symbols=[], dots_are_cons=False))
    code = pair_to_s_exp(code)
    code = to_python(code)
    code = ast.unparse(code)
    return code
