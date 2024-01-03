from dataclasses import dataclass
from functools import cached_property

from s_expression_parser import Pair, nil

from imperative_stitch.to_s import s_exp_parse


@dataclass
class Abstraction:
    body: str
    arity: int

    sym_arity: int
    choice_arity: int

    dfa_root: str
    dfa_symvars: list[str]
    dfa_metavars: list[str]
    dfa_choicevars: list[str]

    @cached_property
    def body_s_expr_direct(self):
        return s_exp_parse(self.body)

    def render_stub(self, arguments):
        print(arguments)
        assert len(arguments) == self.sym_arity + self.arity + self.choice_arity
        substitution = {}
        arguments = list(arguments)[::-1]
        for i in range(self.arity):
            substitution[f"#{i}"] = s_exp_parse(arguments.pop())
        for i in range(self.sym_arity):
            substitution[f"%{i+1}"] = arguments.pop()
            # Pair(
            #     "Name", Pair(arguments.pop(), Pair("Load", nil))
            # )
        for i in range(self.choice_arity):
            substitution[f"?{i}"] = arguments.pop()
        x = self.body_s_expr_direct
        x = substitute(x, substitution)
        return x

    @property
    def is_subseq(self):
        return self.body_s_expr_direct.car == "/subseq"


def substitute(x, substitution):
    if isinstance(x, Pair):
        return Pair(substitute(x.car, substitution), substitute(x.cdr, substitution))
    if isinstance(x, str):
        return substitution.get(x, x)
    if x is nil:
        return nil
    raise ValueError(f"Unsupported node {x}")


def handle_abstractions(name_to_abstr):
    def inject(abstr_name, abstr_args, pair_to_s_exp):
        abst = name_to_abstr[abstr_name]
        o = pair_to_s_exp(abst.body_s_expr(abstr_args))
        return o

    return inject
