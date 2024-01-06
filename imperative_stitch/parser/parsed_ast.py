import ast
import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from s_expression_parser import Pair, nil
from s_expression_parser import ParserConfig, parse

from ..utils.recursion import limit_to_size

from .symbol import Symbol, create_descoper
from .splice import Splice


class ParsedAST(ABC):
    """
    Represents a Parsed AST.
    """

    @classmethod
    def parse_python_code(cls, code):
        # pylint: disable=R0401
        from .parse_python import python_ast_to_parsed_ast

        with limit_to_size(code):
            code = ast.parse(code)
            code = python_ast_to_parsed_ast(code, create_descoper(code))
            return code

    @classmethod
    def parse_s_expression(cls, code):
        with limit_to_size(code):
            # pylint: disable=R0401
            from .parse_s_exp import s_exp_to_parsed_ast

            (code,) = parse(code, ParserConfig(prefix_symbols=[], dots_are_cons=False))
            code = s_exp_to_parsed_ast(code)
            return code

    @abstractmethod
    def to_pair_s_exp(self):
        pass

    @abstractmethod
    def to_python_ast(self):
        pass

    @abstractmethod
    def substitute(self, arguments):
        pass

    @classmethod
    def constant(cls, leaf):
        return NodeAST(
            typ=ast.Constant, children=[LeafAST(leaf=leaf), LeafAST(leaf=None)]
        )

    @classmethod
    def name(cls, name_node):
        assert isinstance(name_node, LeafAST) and isinstance(
            name_node.leaf, Symbol
        ), name_node
        return NodeAST(
            typ=ast.Name,
            children=[
                name_node,
                NodeAST(typ=ast.Load, children=[]),
            ],
        )

    @classmethod
    def call(cls, name_sym, *arguments):
        assert isinstance(name_sym, Symbol), name_sym
        return NodeAST(
            typ=ast.Call,
            children=[
                cls.name(LeafAST(name_sym)),
                ListAST(children=arguments),
                ListAST(children=[]),
            ],
        )

    def render_symvar(self):
        return ParsedAST.call(Symbol(name="__ref__", scope=None), ParsedAST.name(self))

    def render_codevar(self):
        return ParsedAST.call(
            Symbol(name="__code__", scope=None),
            ParsedAST.constant(ast.unparse(self.to_python_ast())),
        )


@dataclass
class SpliceAST(ParsedAST):
    content: ParsedAST

    def to_pair_s_exp(self):
        return list_to_pair(["/splice", self.content.to_pair_s_exp()])

    def to_python_ast(self):
        return Splice(self.content.to_python_ast())

    def substitute(self, arguments):
        return SpliceAST(self.content.substitute(arguments))


@dataclass
class SequenceAST(ParsedAST):
    head: str
    elements: List[ParsedAST]

    def to_pair_s_exp(self):
        result = [self.head] + [x.to_pair_s_exp() for x in self.elements]
        return list_to_pair(result)

    def to_python_ast(self):
        result = []
        for x in self.elements:
            x = x.to_python_ast()
            if isinstance(x, Splice):
                result += x.target
            else:
                result += [x]
        return result

    def substitute(self, arguments):
        return SequenceAST(self.head, [x.substitute(arguments) for x in self.elements])


@dataclass
class NodeAST(ParsedAST):
    typ: type
    children: List[ParsedAST]

    def to_pair_s_exp(self):
        if not self.children:
            return self.typ.__name__

        return list_to_pair(
            [self.typ.__name__] + [x.to_pair_s_exp() for x in self.children]
        )

    def to_python_ast(self):
        out = self.typ(*[x.to_python_ast() for x in self.children])
        out.lineno = 0
        return out

    def substitute(self, arguments):
        return NodeAST(self.typ, [x.substitute(arguments) for x in self.children])


@dataclass
class ListAST(ParsedAST):
    children: List[ParsedAST]

    def to_pair_s_exp(self):
        if not self.children:
            return nil

        return list_to_pair(["list"] + [x.to_pair_s_exp() for x in self.children])

    def to_python_ast(self):
        return [x.to_python_ast() for x in self.children]

    def substitute(self, arguments):
        return ListAST([x.substitute(arguments) for x in self.children])


@dataclass
class LeafAST(ParsedAST):
    leaf: object

    def __post_init__(self):
        assert not isinstance(self.leaf, ParsedAST)

    def to_pair_s_exp(self):
        if (
            self.leaf is True
            or self.leaf is False
            or self.leaf is None
            or self.leaf is Ellipsis
        ):
            return str(self.leaf)
        if isinstance(self.leaf, Symbol):
            return self.leaf.render()
        if isinstance(self.leaf, float):
            return f"f{self.leaf}"
        if isinstance(self.leaf, int):
            return f"i{self.leaf}"
        if isinstance(self.leaf, complex):
            return f"j{self.leaf}"
        if isinstance(self.leaf, str):
            # if all are renderable directly without whitespace, just use that
            if all(
                c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_."
                for c in self.leaf
            ):
                return "s_" + self.leaf
            return "s-" + base64.b64encode(
                str([ord(x) for x in self.leaf]).encode("ascii")
            ).decode("utf-8")
        if isinstance(self.leaf, bytes):
            return "b" + base64.b64encode(self.leaf).decode("utf-8")
        raise RuntimeError(f"invalid leaf: {self.leaf}")

    def to_python_ast(self):
        if isinstance(self.leaf, Symbol):
            return self.leaf.name
        return self.leaf

    def substitute(self, arguments):
        return self


@dataclass
class Variable(ParsedAST):
    sym: str

    @property
    def idx(self):
        return int(self.sym[1:])


@dataclass
class SymvarAST(Variable):
    def to_pair_s_exp(self):
        return self.sym

    def to_python_ast(self):
        return self.sym

    def substitute(self, arguments):
        return arguments.symvars[self.idx - 1]


@dataclass
class MetavarAST(Variable):
    def to_pair_s_exp(self):
        return self.sym

    def to_python_ast(self):
        return ast.Name(id=self.sym)

    def substitute(self, arguments):
        return arguments.metavars[self.idx - 1]


@dataclass
class ChoicevarAST(Variable):
    def to_pair_s_exp(self):
        return self.sym

    def to_python_ast(self):
        return ast.Name(id=self.sym)

    def substitute(self, arguments):
        return arguments.choicevars[self.idx - 1]


@dataclass
class AbstractionCallAST(ParsedAST):
    tag: str
    args: List[ParsedAST]

    def to_pair_s_exp(self):
        return list_to_pair([self.tag] + [x.to_pair_s_exp() for x in self.args])

    def to_python_ast(self):
        raise RuntimeError("cannot convert abstraction call to python")

    def substitute(self, arguments):
        return AbstractionCallAST(
            self.tag, [x.substitute(arguments) for x in self.args]
        )


@dataclass
class NothingAST(ParsedAST):
    def to_pair_s_exp(self):
        return "/nothing"

    def to_python_ast(self):
        return Splice([])

    def substitute(self, arguments):
        return self

    def render_codevar(self):
        return ParsedAST.name(LeafAST(Symbol(name="None", scope=None)))


def list_to_pair(x):
    x = x[:]
    result = nil
    while x:
        result = Pair(x.pop(), result)
    return result
