from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


class ParsedAST(ABC):
    @abstractmethod
    def to_pair_s_exp(self):
        pass


@dataclass
class SequenceAST(ParsedAST):
    head: str
    elements: List[ParsedAST]

    def to_pair_s_exp(self):
        from imperative_stitch.parser.parse import list_to_pair, s_exp_to_pair

        result = [self.head] + [s_exp_to_pair(x) for x in self.elements]
        return list_to_pair(result)
