import ast
import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List
import uuid

from s_expression_parser import Pair, ParserConfig, nil, parse

from ..utils.recursion import limit_to_size
from .splice import Splice
from .symbol import Symbol, create_descoper


class ParsedAST(ABC):
    """
    Represents a Parsed AST.
    """

    @classmethod
    def parse_python_code(cls, code):
        """
        Parse the given python code into a ParsedAST.
        """
        # pylint: disable=R0401
        from .parse_python import python_ast_to_parsed_ast

        with limit_to_size(code):
            code = ast.parse(code)
            code = python_ast_to_parsed_ast(code, create_descoper(code))
            return code

    @classmethod
    def parse_s_expression(cls, code):
        """
        Parse the given s-expression into a ParsedAST.
        """
        with limit_to_size(code):
            # pylint: disable=R0401
            from .parse_s_exp import s_exp_to_parsed_ast

            (code,) = parse(code, ParserConfig(prefix_symbols=[], dots_are_cons=False))
            code = s_exp_to_parsed_ast(code)
            return code

    @abstractmethod
    def to_pair_s_exp(self):
        """
        Convert this ParsedAST into a pair s-expression.
        """

    @abstractmethod
    def to_python_ast(self):
        """
        Convert this ParsedAST into a python AST.
        """

    @abstractmethod
    def map(self, fn):
        """
        Map the given function over this ParsedAST. fn is run in post-order,
            i.e., run on all the children and then on the new object.
        """

    def replace_with_substitute(self, arguments):
        """
        Replace this ParsedAST with the corresponding argument from the given arguments.
        """
        del arguments
        # by default, do nothing
        return self

    def substitute(self, arguments):
        """
        Substitute the given arguments into this ParsedAST.
        """
        return self.map(lambda x: x.replace_with_substitute(arguments))

    @classmethod
    def constant(cls, leaf):
        """
        Create a constant ParsedAST from the given leaf value (which must be a python constant).
        """
        assert not isinstance(leaf, ParsedAST), leaf
        return NodeAST(
            typ=ast.Constant, children=[LeafAST(leaf=leaf), LeafAST(leaf=None)]
        )

    @classmethod
    def name(cls, name_node):
        """
        Create a name ParsedAST from the given name node containing a symbol.
        """
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
        """
        Create a call ParsedAST from the given symbol and arguments.

        In this case, the symbol must be a symbol representing a name.
        """
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
        """
        Render this ParsedAST as a __ref__ variable for stub display, i.e.,
            `a` -> `__ref__(a)`
        """
        return ParsedAST.call(Symbol(name="__ref__", scope=None), ParsedAST.name(self))

    def render_codevar(self):
        """
        Render this ParsedAST as a __code__ variable for stub display, i.e.,
            `a` -> `__code__("a")`
        """
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

    def map(self, fn):
        return fn(SpliceAST(self.content.map(fn)))


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

    def map(self, fn):
        return fn(SequenceAST(self.head, [x.map(fn) for x in self.elements]))


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

    def map(self, fn):
        return fn(NodeAST(self.typ, [x.map(fn) for x in self.children]))


@dataclass
class ListAST(ParsedAST):
    children: List[ParsedAST]

    def to_pair_s_exp(self):
        if not self.children:
            return nil

        return list_to_pair(["list"] + [x.to_pair_s_exp() for x in self.children])

    def to_python_ast(self):
        return [x.to_python_ast() for x in self.children]

    def map(self, fn):
        return fn(ListAST([x.map(fn) for x in self.children]))


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

    def map(self, fn):
        return fn(LeafAST(self.leaf))


@dataclass
class Variable(ParsedAST):
    sym: str

    @property
    def idx(self):
        return int(self.sym[1:])

    def map(self, fn):
        return fn(self)


@dataclass
class SymvarAST(Variable):
    def to_pair_s_exp(self):
        return self.sym

    def to_python_ast(self):
        return self.sym

    def replace_with_substitute(self, arguments):
        return arguments.symvars[self.idx - 1]


@dataclass
class MetavarAST(Variable):
    def to_pair_s_exp(self):
        return self.sym

    def to_python_ast(self):
        return ast.Name(id=self.sym)

    def replace_with_substitute(self, arguments):
        return arguments.metavars[self.idx - 1]


@dataclass
class ChoicevarAST(Variable):
    def to_pair_s_exp(self):
        return self.sym

    def to_python_ast(self):
        return ast.Name(id=self.sym)

    def replace_with_substitute(self, arguments):
        return arguments.choicevars[self.idx - 1]


@dataclass
class AbstractionCallAST(ParsedAST):
    tag: str
    args: List[ParsedAST]
    handle: uuid.UUID = field(default_factory=uuid.uuid4)

    def to_pair_s_exp(self):
        return list_to_pair([self.tag] + [x.to_pair_s_exp() for x in self.args])

    def to_python_ast(self):
        raise RuntimeError("cannot convert abstraction call to python")

    def map(self, fn):
        return fn(AbstractionCallAST(self.tag, [x.map(fn) for x in self.args]))


@dataclass
class NothingAST(ParsedAST):
    def to_pair_s_exp(self):
        return "/nothing"

    def to_python_ast(self):
        return Splice([])

    def substitute(self, arguments):
        return self

    def map(self, fn):
        return fn(self)

    def render_codevar(self):
        return ParsedAST.name(LeafAST(Symbol(name="None", scope=None)))


def list_to_pair(x):
    x = x[:]
    result = nil
    while x:
        result = Pair(x.pop(), result)
    return result
