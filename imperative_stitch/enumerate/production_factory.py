import copy

from dataclasses import dataclass, field
from typing import List, Dict

from ..parser.parsed_ast import ParsedAST, AbstractionCallAST

from ..enumerate.ordering import order_replacements_map
from ..enumerate.production import *


@dataclass
class Config:
    render_programs: bool = True
    render_abstractions: bool = False
    render_params: bool = False

    def render(self, production: Production):
        assert isinstance(production, Production)
        if isinstance(production, ProgramProduction):
            return self.render_programs
        if isinstance(production, AbstractionProduction):
            return self.render_abstractions
        if isinstance(production, ParamProduction):
            return self.render_params
        return True


@dataclass
class ProductionFactory:
    programs: Dict[str, ProgramProduction] = field(default_factory=dict)
    abstractions: Dict[str, AbstractionProduction] = field(default_factory=dict)
    params: Dict[str, ParamProduction] = field(default_factory=dict)
    vars: Dict[str, VarProduction] = field(default_factory=dict)
    # mapping from code segments to their corresponding params
    # used to make param lookups during rewrite easier
    _code_to_params: Dict[str, ParamProduction] = field(default_factory=dict)

    def get_production(self, name_or_code):
        if name_or_code in self.abstractions:
            return self.abstractions[name_or_code]
        if name_or_code in self.programs:
            return self.programs[name_or_code]
        if name_or_code in self._code_to_params:
            return self._code_to_params[name_or_code]
        if name_or_code in self.params:
            return self.params[name_or_code]
        return self.vars[name_or_code]

    def is_production(self, name_or_code):
        return (
            name_or_code in self.abstractions
            or name_or_code in self.programs
            or name_or_code in self._code_to_params
            or name_or_code in self.params
            or name_or_code in self.vars
        )

    def add_abstractions(self, abstraction_list):
        for fn in abstraction_list:
            production = AbstractionProduction(f"fn_{len(self.abstractions) + 1}", fn)
            self.abstractions[production.name] = production

    def add_programs(self, programs: List[str]):
        for program in programs:
            self.add_program(program)

    def add_solution(self, program: str):
        assert isinstance(program, str)
        self.add_program(program, is_solution=True)

    def add_program(self, s_exprs: str, is_solution=False):
        name = f"fn_program_{len(self.programs)+1}"
        program = ProgramProduction(
            name, ParsedAST.parse_s_expression(s_exprs), is_solution
        )
        self.programs[name] = program

        for fn in program.ast.abstraction_calls().values():
            self.add_params(fn)

    def add_params(self, abstraction_call: AbstractionCallAST):
        production = self.get_production(abstraction_call.tag)
        for i, param in enumerate(abstraction_call.args):
            nested_abstractions = param.abstraction_calls()
            body = param.replace_abstraction_calls(
                {
                    k: ParsedAST.parse_s_expression(f"({v.tag})")
                    for k, v in nested_abstractions.items()
                }
            )
            self.make_param_var(body, production, i)
            for arg in param.abstraction_calls().values():
                self.add_params(arg)

    def make_param_var(self, ast, production: AbstractionProduction, idx: int):
        body = ast.to_s_exp()
        if self.is_production(body):
            return
        if body.startswith("&"):
            production = VarProduction(body, ast)
            self.vars[production.name] = production
            return
        name = f"fn_param_{len(self._code_to_params)}"
        production = ParamProduction(name, ast, production.arg_dfa_root(idx))
        self._code_to_params[body] = production
        self.params[name] = production

    def expand_programs(self, include_sols=False) -> List[ParsedAST]:
        output = []
        abstrs = {k: v.ast for k, v in self.abstractions.items()}
        for program in self.programs.values():
            if program.is_solution and not include_sols:
                continue
            output.append(program.ast.abstraction_calls_to_bodies(abstrs))
        return output

    def render(self, s_expr: str):
        rendered = self._render(ParsedAST.parse_s_expression(s_expr))
        return rendered.to_s_exp()

    def _render(self, ast: ParsedAST):
        abstraction_calls = ast.abstraction_calls()
        handle_to_replacement = {}
        for id, abstraction_call in abstraction_calls.items():
            production = self.get_production(abstraction_call.tag)
            args = [self._render(arg) for arg in abstraction_call.args]
            handle_to_replacement[id] = production.apply(args)

        ast = ast.replace_abstraction_calls(handle_to_replacement)

        return ast

    def rewrite_all(self, config=Config(), include_sols=False):
        output = []
        for p in self.programs.values():
            if not include_sols and p.is_solution:
                continue
            rewritten = self.rewrite_program(p, p.ast, config=config)
            output.append(rewritten)
        return output

    def rewrite_program(self, production: Production, ast, config: Config):
        all_fns = ast.abstraction_calls()
        handle_to_replacement = {}

        for handle, ast_call in all_fns.items():
            handle_to_replacement[handle] = self.rewrite_param(ast_call, config)

        if config.render(production):
            ast_handle_to_replacement = {
                k: ParsedAST.parse_s_expression(v)
                for k, v in handle_to_replacement.items()
            }
            return ast.replace_abstraction_calls(ast_handle_to_replacement).to_s_exp()

        return production.render(order_replacements_map(ast, handle_to_replacement))

    def rewrite_param(self, ast: AbstractionCallAST, config=Config()):
        args, abstraction = [], self.get_production(ast.tag)
        for raw_param in ast.args:
            abst_calls = raw_param.abstraction_calls()
            handle_to_replacements = {
                k: ParsedAST.parse_s_expression(f"({v.tag})")
                for k, v in abst_calls.items()
            }
            param = raw_param.replace_abstraction_calls(handle_to_replacements)
            production = self.get_production(param.to_s_exp())
            assert isinstance(raw_param, ParsedAST)
            args.append(self.rewrite_program(production, raw_param, config))
        if config.render(abstraction):
            return abstraction.ast.substitute_body(
                [ParsedAST.parse_s_expression(a) for a in args]
            ).to_s_exp()
        return abstraction.render(args)

    def rewrite_solutions(self, config=Config(), limit=None) -> List[str]:
        solutions = [p for p in self.programs.values() if p.is_solution]
        if not solutions:
            return None
        if limit:
            solutions = solutions[:limit]
        return [self.rewrite_program(sol, sol.ast, config) for sol in solutions]

    def rewrite_solution(self, config=Config()) -> str:
        return self.rewrite_solutions(config, limit=1)[0]

    def expand_dfa(self, dfa):
        dfa = copy.deepcopy(dfa)
        for name, param in self.params.items():
            root = param.dfa_root
            children = [
                self.get_production(abstraction.tag)
                for abstraction in param.ast.abstraction_calls().values()
            ]
            dfa[root][name] = [abstraction.ast.dfa_root for abstraction in children]
        return dfa


def initialize_factory(abstractions, programs, solution):
    factory = ProductionFactory()
    factory.add_abstractions(abstractions)
    factory.add_programs(programs)
    factory.add_solution(solution)
    return factory
