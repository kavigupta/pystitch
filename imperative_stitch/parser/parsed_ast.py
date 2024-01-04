import ast
import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from s_expression_parser import Pair, nil

from .symbol import Symbol
from .splice import Splice


class ParsedAST(ABC):
    @abstractmethod
    def to_pair_s_exp(self):
        pass

    @abstractmethod
    def to_python_ast(self):
        pass


class SpliceAST(ParsedAST):
    content: ParsedAST

    def to_pair_s_exp(self):
        return list_to_pair(["/splice", self.content.to_pair_s_exp()])

    def to_python_ast(self):
        return Splice(self.content.to_python_ast())


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
                result += x.elements
            else:
                result += [x]
        return result


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


@dataclass
class ListAST(ParsedAST):
    children: List[ParsedAST]

    def to_pair_s_exp(self):
        if not self.children:
            return nil

        return list_to_pair(["list"] + [x.to_pair_s_exp() for x in self.children])

    def to_python_ast(self):
        return [x.to_python_ast() for x in self.children]


@dataclass
class LeafAST(ParsedAST):
    leaf: object

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


@dataclass
class SymvarAST(ParsedAST):
    sym: str

    def to_pair_s_exp(self):
        return self.sym

    def to_python_ast(self):
        return self.sym


@dataclass
class MetavarAST(ParsedAST):
    sym: str

    def to_pair_s_exp(self):
        return self.sym

    def to_python_ast(self):
        return ast.Name(id=self.sym)


@dataclass
class ChoicevarAST(ParsedAST):
    sym: str

    def to_pair_s_exp(self):
        return self.sym

    def to_python_ast(self):
        return ast.Name(id=self.sym)


@dataclass
class AbstractionCallAST(ParsedAST):
    tag: str
    args: List[ParsedAST]

    def to_pair_s_exp(self):
        return list_to_pair([self.tag] + [x.to_pair_s_exp() for x in self.args])

    def to_python_ast(self):
        args = [
            ast.Name(sym, ast.Load) if isinstance(sym, str) else sym
            for sym in self.args
        ]
        return ast.Call(ast.Name(self.tag, ast.Load()), args, [])


def list_to_pair(x):
    x = x[:]
    result = nil
    while x:
        result = Pair(x.pop(), result)
    return result
