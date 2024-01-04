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

from imperative_stitch.parser.parsed_ast import (
    AbstractionCallAST,
    ChoicevarAST,
    LeafAST,
    ListAST,
    MetavarAST,
    NodeAST,
    SequenceAST,
    SpliceAST,
    SymvarAST,
)
from imperative_stitch.utils.ast_utils import field_is_body, name_field, true_globals
from imperative_stitch.utils.recursion import recursionlimit

from .symbol import Symbol


def python_ast_to_parsed_ast(x, descoper, is_body=False):
    if is_body:
        assert isinstance(x, list), str(x)
        x = [python_ast_to_parsed_ast(x, descoper) for x in x]
        return SequenceAST("/seq", x)
    if isinstance(x, ast.AST):
        result = []
        for f in x._fields:
            el = getattr(x, f)
            if x in descoper and f == name_field(x):
                assert isinstance(el, str), (x, f, el)
                result.append(LeafAST(Symbol(el, descoper[x])))
            else:
                result.append(
                    python_ast_to_parsed_ast(
                        el, descoper, is_body=field_is_body(type(x), f)
                    )
                )
        return NodeAST(type(x), result)
    if isinstance(x, list):
        return ListAST([python_ast_to_parsed_ast(x, descoper) for x in x])
    if x is None or x is Ellipsis or isinstance(x, (int, float, complex, str, bytes)):
        return LeafAST(x)
    raise ValueError(f"Unsupported node {x}")


def pair_to_list(x):
    result = []
    while x is not nil:
        result.append(x.car)
        x = x.cdr
    return result


def s_exp_leaf_to_value(x):
    """
    Returns (True, a python representation of the leaf) if it is a leaf, or (False, None) otherwise.
    """
    sym_x = Symbol.parse(x)
    if sym_x is not None:
        return True, sym_x
    if x == "Ellipsis":
        return True, Ellipsis
    if x in {"True", "False", "None"}:
        return True, ast.literal_eval(x)
    if x.startswith("i"):
        return True, int(x[1:])
    if x.startswith("f"):
        return True, float(x[1:])
    if x.startswith("j"):
        return True, complex(x[1:])
    if x.startswith("s_"):
        return True, x[2:]
    if x.startswith("s-"):
        return True, "".join(
            chr(x)
            for x in ast.literal_eval(
                base64.b64decode(x[2:].encode("utf-8")).decode("ascii")
            )
        )
    if x.startswith("b"):
        return True, base64.b64decode(x[1:].encode("utf-8"))

    return False, None


def pair_to_s_exp(x):
    if x is nil or x == "nil":
        return ListAST([])
    if isinstance(x, str):
        if x.startswith("%"):
            return SymvarAST(x)
        if x.startswith("#"):
            return MetavarAST(x)
        if x.startswith("?"):
            return ChoicevarAST(x)

        is_leaf, leaf = s_exp_leaf_to_value(x)
        if is_leaf:
            return LeafAST(leaf)
        typ = getattr(ast, x)
        assert not typ._fields
        return NodeAST(typ, [])
    assert isinstance(x, Pair), str(type(x))
    tag, *args = pair_to_list(x)
    assert isinstance(tag, str), str(tag)
    args = [pair_to_s_exp(x) for x in args]
    if tag in {"/seq", "/subseq"}:
        return SequenceAST(tag, args)
    if tag in {"/splice"}:
        [arg] = args
        return SpliceAST(arg)
    if tag in {"list"}:
        print(args)
        return ListAST(args)
    if tag.startswith("fn"):
        return AbstractionCallAST(tag, args)
    return NodeAST(getattr(ast, tag), args)


def parse_to_list_s_expression(code):
    with recursionlimit(max(1500, len(code))):
        code = ast.parse(code)
        code = python_ast_to_parsed_ast(code, create_descoper(code))
        return code


def python_to_s_exp(code, renderer_kwargs=None):
    if renderer_kwargs is None:
        renderer_kwargs = {}
    with recursionlimit(max(1500, len(code))):
        code = parse_to_list_s_expression(code)
        code = code.to_pair_s_exp()
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
        code = code.to_python_ast()
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
