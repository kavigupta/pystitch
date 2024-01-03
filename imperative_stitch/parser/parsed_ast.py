from abc import ABC, abstractmethod
import base64
from dataclasses import dataclass
from typing import List

from s_expression_parser import nil

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
        from imperative_stitch.parser.parse import list_to_pair

        result = [self.head] + [x.to_pair_s_exp() for x in self.elements]
        return list_to_pair(result)


@dataclass
class NodeAST(ParsedAST):
    typ: type
    children: List[ParsedAST]

    def to_pair_s_exp(self):
        from imperative_stitch.parser.parse import list_to_pair

        if not self.children:
            return self.typ.__name__

        return list_to_pair(
            [self.typ.__name__] + [x.to_pair_s_exp() for x in self.children]
        )


@dataclass
class ListAST(ParsedAST):
    children: List[ParsedAST]

    def to_pair_s_exp(self):
        from imperative_stitch.parser.parse import list_to_pair

        if not self.children:
            return nil

        return list_to_pair(
            ["list"] + [x.to_pair_s_exp() for x in self.children]
        )


@dataclass
class LeafAST(ParsedAST):
    leaf: object

    def to_pair_s_exp(self):
        x = self.leaf
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
            return "s-" + base64.b64encode(
                str([ord(x) for x in x]).encode("ascii")
            ).decode("utf-8")
        if isinstance(x, bytes):
            return "b" + base64.b64encode(x).decode("utf-8")
        raise RuntimeError("bad")
