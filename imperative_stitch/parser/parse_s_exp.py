import ast
import base64

from s_expression_parser import Pair, nil

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

from .symbol import Symbol


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


def s_exp_to_parsed_ast(x):
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
    args = [s_exp_to_parsed_ast(x) for x in args]
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
