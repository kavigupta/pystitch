import ast
import base64
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Union

import neurosym as ns
from frozendict import frozendict
from increase_recursionlimit import increase_recursionlimit

from .splice import Splice
from .symbol import PythonSymbol


class PythonAST(ABC):
    """
    Represents a Parsed AST.
    """

    @abstractmethod
    def to_ns_s_exp(self, config=frozendict()) -> ns.SExpression:
        """
        Convert this PythonAST into a pair s-expression.
        """

    def to_python(self) -> str:
        """
        Convert this PythonAST into python code.
        """
        with increase_recursionlimit():
            code = self.to_python_ast()
            if isinstance(code, Splice):
                code = code.target
            return ast.unparse(code)

    @abstractmethod
    def to_python_ast(self) -> ast.AST:
        """
        Convert this PythonAST into a python AST.
        """

    @abstractmethod
    def map(self, fn):
        """
        Map the given function over this PythonAST. fn is run in post-order,
            i.e., run on all the children and then on the new object.
        """


@dataclass
class SequenceAST(PythonAST):
    head: str
    elements: List[PythonAST]

    def __post_init__(self):
        assert isinstance(self.head, str), self.head
        assert all(isinstance(x, PythonAST) for x in self.elements), self.elements

    def to_ns_s_exp(self, config=frozendict()):
        return ns.SExpression(self.head, [x.to_ns_s_exp(config) for x in self.elements])

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
class NodeAST(PythonAST):
    typ: type
    children: List[PythonAST]

    def to_ns_s_exp(self, config=frozendict()):
        if not self.children and not config.get("no_leaves", False):
            return self.typ.__name__

        return ns.SExpression(
            self.typ.__name__, [x.to_ns_s_exp(config) for x in self.children]
        )

    def to_python_ast(self):
        out = self.typ(*[x.to_python_ast() for x in self.children])
        out.lineno = 0
        return out

    def map(self, fn):
        return fn(NodeAST(self.typ, [x.map(fn) for x in self.children]))


@dataclass
class ListAST(PythonAST):
    children: List[PythonAST]

    def to_ns_s_exp(self, config=frozendict()):
        if not self.children:
            return (
                ns.SExpression("list", []) if config.get("no_leaves", False) else "nil"
            )

        return ns.SExpression("list", [x.to_ns_s_exp(config) for x in self.children])

    def to_python_ast(self):
        return [x.to_python_ast() for x in self.children]

    def map(self, fn):
        return fn(ListAST([x.map(fn) for x in self.children]))


@dataclass
class LeafAST(PythonAST):
    leaf: object

    def __post_init__(self):
        assert not isinstance(self.leaf, PythonAST)

    def to_ns_s_exp(self, config=frozendict()):
        leaf_as_string = self.render_leaf_as_string()
        if not config.get("no_leaves", False):
            return leaf_as_string
        return ns.SExpression("const-" + leaf_as_string, [])

    def render_leaf_as_string(self):
        if (
            self.leaf is True
            or self.leaf is False
            or self.leaf is None
            or self.leaf is Ellipsis
        ):
            return str(self.leaf)
        if isinstance(self.leaf, PythonSymbol):
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
        if isinstance(self.leaf, PythonSymbol):
            return self.leaf.name
        return self.leaf

    def map(self, fn):
        return fn(LeafAST(self.leaf))


@dataclass
class Variable(PythonAST):
    sym: str

    @property
    def idx(self):
        return int(self.sym[1:])

    def map(self, fn):
        return fn(self)

    def to_ns_s_exp(self, config=frozendict()):
        if config.get("no_leaves", False):
            return ns.SExpression("var-" + self.sym, [])
        return self.sym


@dataclass
class SymvarAST(Variable):
    def to_python_ast(self):
        return self.sym

    def _replace_with_substitute(self, arguments):
        return arguments.symvars[self.idx - 1]


@dataclass
class MetavarAST(Variable):
    def to_python_ast(self):
        return ast.Name(id=self.sym)

    def _replace_with_substitute(self, arguments):
        return arguments.metavars[self.idx]


@dataclass
class ChoicevarAST(Variable):
    def to_python_ast(self):
        return ast.Name(id=self.sym)

    def _replace_with_substitute(self, arguments):
        return SpliceAST(arguments.choicevars[self.idx])


@dataclass
class AbstractionCallAST(PythonAST):
    tag: str
    args: List[PythonAST]
    handle: uuid.UUID

    def to_ns_s_exp(self, config=frozendict()):
        return ns.SExpression(self.tag, [x.to_ns_s_exp(config) for x in self.args])

    def to_python_ast(self):
        raise RuntimeError("cannot convert abstraction call to python")

    def map(self, fn):
        return fn(
            AbstractionCallAST(self.tag, [x.map(fn) for x in self.args], self.handle)
        )


@dataclass
class SliceElementAST(PythonAST):
    content: PythonAST

    @classmethod
    def of(cls, x):
        if isinstance(x, SliceElementAST):
            return x
        return SliceElementAST(x)

    def to_ns_s_exp(self, config=frozendict()):
        # should not be necessary; since we have the assertion
        # but pylint is not smart enough to figure that out
        # pylint: disable=no-member
        content = self.content
        if isinstance(self.content, StarrableElementAST):
            # safe because it is not actually legal to have a starred element
            # in a slice
            content = content.content
        assert isinstance(content, (NodeAST, AbstractionCallAST, Variable)), content
        if isinstance(content, NodeAST):
            if content.typ is ast.Slice:
                return ns.SExpression("_slice_slice", [content.to_ns_s_exp(config)])
            if content.typ is ast.Tuple:
                assert isinstance(content.children, list)
                assert len(content.children) == 2
                content_children = list(content.children)
                content_children[0] = ListAST(
                    [SliceElementAST.of(x) for x in content_children[0].children]
                )
                content = NodeAST(typ=ast.Tuple, children=content_children)

                return ns.SExpression("_slice_tuple", [content.to_ns_s_exp(config)])
        return ns.SExpression("_slice_content", [content.to_ns_s_exp(config)])

    def to_python_ast(self):
        return self.content.to_python_ast()

    def map(self, fn):
        return fn(SliceElementAST(self.content.map(fn)))


@dataclass
class StarrableElementAST(PythonAST):
    content: PythonAST

    def to_ns_s_exp(self, config=frozendict()):
        # pylint: disable=no-member
        assert isinstance(
            self.content, (NodeAST, AbstractionCallAST, Variable)
        ), self.content
        if isinstance(self.content, NodeAST) and self.content.typ is ast.Starred:
            return ns.SExpression(
                "_starred_starred", [self.content.to_ns_s_exp(config)]
            )
        return ns.SExpression("_starred_content", [self.content.to_ns_s_exp(config)])

    def to_python_ast(self):
        return self.content.to_python_ast()

    def map(self, fn):
        return fn(StarrableElementAST(self.content.map(fn)))


@dataclass
class SpliceAST(PythonAST):
    content: Union[SequenceAST, AbstractionCallAST]

    def __post_init__(self):
        assert isinstance(
            self.content, (SequenceAST, AbstractionCallAST, Variable)
        ), self.content

    def to_ns_s_exp(self, config=frozendict()):
        return ns.SExpression("/splice", [self.content.to_ns_s_exp(config)])

    def to_python_ast(self):
        return Splice(self.content.to_python_ast())

    def map(self, fn):
        return fn(SpliceAST(self.content.map(fn)))
