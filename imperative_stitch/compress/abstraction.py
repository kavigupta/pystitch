from dataclasses import dataclass

from imperative_stitch.parser import ParsedAST
from imperative_stitch.parser.symbol import Symbol


@dataclass
class Arguments:
    """
    Represents the arguments to an abstraction function. This is a list of metavariables,
        symbol variables, and choice variables.
    """

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
        """
        Produce an Arguments object from a list of arguments.
        """
        return Arguments.from_list(
            arguments, self.arity, self.sym_arity, self.choice_arity
        )

    def create_stub(self, arguments):
        """
        Create a stub of this abstraction with the given arguments. The stub looks something
            like `fn_1(__code__("a + b"), __ref__(a), __ref__(z), __code("x = 2 + 3"))`,
            where the metavariables and choice variables are __code__, and the symbol
            variables are __ref__.
        """
        arguments = self.process_arguments(arguments)
        args_list = arguments.render_list()
        return ParsedAST.call(
            Symbol(name=self.name, scope=None),
            *args_list,
        )

    def substitute_body(self, arguments):
        """
        Substitute the given arguments into the body of this abstraction.
        """
        arguments = self.process_arguments(arguments)
        return self.body.substitute(arguments)


def handle_abstractions(name_to_abstr):
    """
    Given a dictionary mapping abstraction names to Abstraction objects, return a function
        that can be used to inject abstractions into a ParsedAST.
    """

    def inject(abstr_name, abstr_args, pair_to_s_exp):
        abst = name_to_abstr[abstr_name]
        o = pair_to_s_exp(abst.body_s_expr(abstr_args))
        return o

    return inject
