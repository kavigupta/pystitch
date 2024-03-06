from dataclasses import dataclass

from imperative_stitch.parser import ParsedAST
from imperative_stitch.parser.parsed_ast import LeafAST, SequenceAST, SpliceAST
from imperative_stitch.parser.symbol import Symbol


@dataclass
class Arguments:
    """
    Represents the arguments to an abstraction function. This is a list of metavariables,
        symbol variables, and choice variables.
    """

    metavars: list[ParsedAST]
    symvars: list[ParsedAST]
    choicevars: list[SequenceAST]

    def __post_init__(self):
        assert all(isinstance(x, ParsedAST) for x in self.metavars), self.metavars
        assert all(isinstance(x, ParsedAST) for x in self.symvars), self.symvars
        assert all(isinstance(x, SequenceAST) for x in self.choicevars), self.choicevars

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

    def __post_init__(self):
        assert self.arity == len(self.dfa_metavars)
        assert self.sym_arity == len(self.dfa_symvars)
        assert self.choice_arity == len(self.dfa_choicevars)

        assert self.dfa_root in ["E", "S", "seqS"]

        assert isinstance(self.body, ParsedAST), self.body

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
        e_stub = ParsedAST.call(
            Symbol(name=self.name, scope=None),
            *args_list,
        )
        if self.dfa_root == "E":
            return e_stub
        s_stub = ParsedAST.expr_stmt(e_stub)
        if self.dfa_root == "S":
            return s_stub
        seq_stub = SequenceAST("/seq", [s_stub])
        assert self.dfa_root == "seqS"
        return seq_stub

    def _add_extract_pragmas(self, body):
        if self.dfa_root == "E":
            raise ValueError("Cannot add extract pragmas to an expression")
        start_pragma = ParsedAST.parse_python_statement("__start_extract__")
        end_pragma = ParsedAST.parse_python_statement("__end_extract__")
        if self.dfa_root == "S":
            return SpliceAST(SequenceAST("/seq", [start_pragma, body, end_pragma]))
        assert self.dfa_root == "seqS"
        return SequenceAST("/seq", [start_pragma, *body.elements, end_pragma])

    def substitute_body(self, arguments, *, pragmas=False):
        """
        Substitute the given arguments into the body of this abstraction.
        """
        if not isinstance(arguments, Arguments):
            arguments = self.process_arguments(arguments)
        if pragmas:
            if not all(x == "E" for x in self.dfa_metavars):
                raise ValueError(
                    "Cannot add extract pragmas to a body with non-expression metavariables"
                )
            if not all(x == "seqS" for x in self.dfa_choicevars):
                raise ValueError(
                    "Cannot add extract pragmas to a body with non-statement choicevars"
                )
            arguments = Arguments(
                [
                    x.wrap_in_metavariable(f"__m{i}")
                    for i, x in enumerate(arguments.metavars)
                ],
                arguments.symvars,
                [x.wrap_in_choicevar() for x in arguments.choicevars],
            )
        body = self.body
        body = body.substitute(arguments)
        if pragmas:
            body = self._add_extract_pragmas(body)
        return body

    def body_with_variable_names(self, *, pragmas=False):
        """
        Render the body but with the #0, %0, ?0, kept as placeholders.
        """
        arguments = Arguments(
            [ParsedAST.name(LeafAST(Symbol(f"#{i}", None))) for i in range(self.arity)],
            [LeafAST(Symbol(f"%{i + 1}", None)) for i in range(self.sym_arity)],
            [
                SequenceAST(
                    "/seq",
                    [ParsedAST.expr_stmt(ParsedAST.name(LeafAST(Symbol(f"?{i}", None))))]
                )
                for i in range(self.choice_arity)
            ],
        )
        return self.substitute_body(arguments, pragmas=pragmas)


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
