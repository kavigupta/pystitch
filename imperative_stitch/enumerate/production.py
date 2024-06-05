from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any


from ..compress.abstraction import Abstraction
from ..parser import ParsedAST

from ..enumerate.ordering import map_ordered_replacements


@dataclass
class Production(ABC):
    name: str

    @abstractmethod
    def get_rule(self) -> str:
        pass

    def render(self, args) -> str:
        output = f"({self.name}"
        for c in args:
            output += f" {c}"
        output += ")"
        return output

    @classmethod
    def apply(self, params: List[str]) -> str:
        pass


@dataclass
class ProgramProduction(Production):
    ast: ParsedAST
    is_solution: bool = False
    dfa_root: str = "M"

    def __post_init__(self):
        self.body = self.ast.to_s_exp()
        self.num_args = len(self.ast.abstraction_calls())

    def get_rule(self):
        args = ["i"] * self.num_args
        return f"({', '.join(args)}) -> i"

    def apply(self, args) -> str:
        handle_to_replacement = map_ordered_replacements(self.ast, args)
        return self.ast.replace_abstraction_calls(handle_to_replacement)


@dataclass
class AbstractionProduction(Production):
    config: Dict[str, Any]

    def __post_init__(self):
        init = {k: v for k, v in self.config.items() if k != "body"}
        self.body = ParsedAST.parse_s_expression(self.config["body"])
        self.ast = Abstraction(self.name, self.body, **init)
        self.dfa_root = self.ast.dfa_root
        self.dfa_roots_for_args = (
            init["dfa_metavars"] + init["dfa_symvars"] + init["dfa_choicevars"]
        )
        self.num_args = init["arity"] + init["sym_arity"] + init["choice_arity"]

    def get_rule(self):
        args = ["i"] * self.num_args
        return f"({', '.join(args)}) -> i"

    def arg_dfa_root(self, index):
        return self.dfa_roots_for_args[index]

    def apply(self, args: List[ParsedAST]) -> str:
        assert len(args) == self.num_args
        return self.ast.substitute_body(args)

    def set_ast(self, new_ast: Abstraction):
        self.ast = new_ast
        self.body = new_ast.body


@dataclass
class ParamProduction(Production):
    ast: ParsedAST
    dfa_root: str

    def __post_init__(self):
        self.num_args = len(self.ast.abstraction_calls())

    def get_rule(self):
        args = ["i"] * self.num_args
        return f"({', '.join(args)}) -> i"

    def apply(self, args):
        handle_to_replacement = map_ordered_replacements(self.ast, args)
        substituted = self.ast.replace_abstraction_calls(handle_to_replacement)
        return substituted.to_s_exp()


@dataclass
class VarProduction(Production):
    ast: ParsedAST
    dfa_root: str = "Name"
    num_args: int = 0

    def get_rule(self) -> str:
        assert len(self.num_args) == 0
        return "() -> i"

    def render(self, args):
        assert len(args) == 0
        return self.name

    def apply(self, args) -> str:
        assert len(args) == 0
        return self.ast.to_s_exp()
