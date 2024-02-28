import ast
import base64
import uuid

import neurosym as ns

from imperative_stitch.parser.parsed_ast import (
    AbstractionCallAST,
    ChoicevarAST,
    LeafAST,
    ListAST,
    MetavarAST,
    NodeAST,
    NothingAST,
    SequenceAST,
    SliceElementAST,
    SpliceAST,
    StarrableElementAST,
    SymvarAST,
)

from .symbol import Symbol


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


def s_exp_to_parsed_ast(x: ns.SExpression):
    """
    Convert an s-expression (as pairs) to a parsed AST
    """
    if x == "nil":
        return ListAST([])
    if isinstance(x, str):
        if x.startswith("%"):
            return SymvarAST(x)
        if x.startswith("#"):
            return MetavarAST(x)
        if x.startswith("?"):
            return ChoicevarAST(x)
        if x in {"/nothing"}:
            return NothingAST()

        is_leaf, leaf = s_exp_leaf_to_value(x)
        if is_leaf:
            return LeafAST(leaf)
        typ = getattr(ast, x)
        assert not typ._fields
        return NodeAST(typ, [])
    assert isinstance(x, ns.SExpression), str((type(x), x))
    tag, args = x.symbol, x.children
    # remove any type information
    tag = tag.split(".")[0]
    if tag.startswith("const-"):
        assert len(args) == 0
        is_leaf, leaf = s_exp_leaf_to_value(tag[len("const-") :])
        assert is_leaf
        return LeafAST(leaf)
    assert isinstance(tag, str), str(tag)
    args = [s_exp_to_parsed_ast(x) for x in args]
    if tag in {"/seq", "/subseq"}:
        return SequenceAST(tag, args)
    if tag in {"/splice"}:
        [arg] = args
        return SpliceAST(arg)
    if tag.startswith("_slice"):
        assert len(args) == 1
        return SliceElementAST(args[0])
    if tag.startswith("_starred"):
        assert len(args) == 1
        return StarrableElementAST(args[0])
    if tag in {"list"}:
        return ListAST(args)
    if tag.startswith("fn"):
        return AbstractionCallAST(tag, args, uuid.uuid4())
    return NodeAST(getattr(ast, tag), args)
