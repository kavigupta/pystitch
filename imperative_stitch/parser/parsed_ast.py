import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from s_expression_parser import Pair, nil

from .symbol import Symbol


class ParsedAST(ABC):
    @abstractmethod
    def to_pair_s_exp(self):
        pass


@dataclass
class SequenceAST(ParsedAST):
    head: str
    elements: List[ParsedAST]

    def to_pair_s_exp(self):
        result = [self.head] + [x.to_pair_s_exp() for x in self.elements]
        return list_to_pair(result)


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


@dataclass
class ListAST(ParsedAST):
    children: List[ParsedAST]

    def to_pair_s_exp(self):
        if not self.children:
            return nil

        return list_to_pair(["list"] + [x.to_pair_s_exp() for x in self.children])


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


def list_to_pair(x):
    x = x[:]
    result = nil
    while x:
        result = Pair(x.pop(), result)
    return result
