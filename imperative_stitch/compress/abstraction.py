from dataclasses import dataclass

from imperative_stitch.parser import ParsedAST
from imperative_stitch.parser.symbol import Symbol


@dataclass
class Arguments:
    metavars: list[ParsedAST]
    symvars: list[ParsedAST]
    choicevars: list[ParsedAST]

    @classmethod
    def from_list(cls, arguments, arity, sym_arity, choice_arity):
        assert len(arguments) == arity + sym_arity + choice_arity
        metavars, symvars, choicevars = (
            arguments[:arity],
            arguments[arity : arity + sym_arity],
            arguments[arity + sym_arity :],
        )
        return cls(metavars, symvars, choicevars)

    def render_list(self):
        return (
            [x.render_codevar() for x in self.metavars]
            + [x.render_symvar() for x in self.symvars]
            + [x.render_codevar() for x in self.choicevars]
        )


@dataclass
class Abstraction:
    name: str
    body: ParsedAST
    arity: int

    sym_arity: int
    choice_arity: int

    dfa_root: str
    dfa_symvars: list[str]
    dfa_metavars: list[str]
    dfa_choicevars: list[str]

    def process_arguments(self, arguments):
        return Arguments.from_list(
            arguments, self.arity, self.sym_arity, self.choice_arity
        )

    def create_stub(self, arguments):
        arguments = self.process_arguments(arguments)
        args_list = arguments.render_list()
        return ParsedAST.call(
            Symbol(name=self.name, scope=None),
            *args_list,
        )

    def substitute_body(self, arguments):
        arguments = self.process_arguments(arguments)
        return self.body.substitute(arguments)


def handle_abstractions(name_to_abstr):
    def inject(abstr_name, abstr_args, pair_to_s_exp):
        abst = name_to_abstr[abstr_name]
        o = pair_to_s_exp(abst.body_s_expr(abstr_args))
        return o

    return inject
