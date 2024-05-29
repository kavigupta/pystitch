import uuid
from typing import Union

import neurosym as ns

from imperative_stitch.parser.patterns import VARIABLE_PATTERN
from imperative_stitch.utils.types import non_sequence_prefixes

from .python_ast import (
    AbstractionCallAST,
    ChoicevarAST,
    MetavarAST,
    PythonAST,
    SymvarAST,
)

var_hooks = {
    "%": SymvarAST,
    "#": MetavarAST,
    "?": ChoicevarAST,
}


def hook_for_var(hook, change_tag=lambda x: x):
    return lambda tag, _: hook(change_tag(tag))


node_hooks = {
    "fn_": lambda tag, args: AbstractionCallAST(tag, args, uuid.uuid4()),
    **{
        f"var-{leaf}": hook_for_var(
            hook, lambda tag: VARIABLE_PATTERN.match(tag).group("name")
        )
        for leaf, hook in var_hooks.items()
    },
    **{leaf: hook_for_var(hook) for leaf, hook in var_hooks.items()},
}


python_to_s_exp = ns.python_to_s_exp


def s_exp_to_python(code: Union[str, ns.SExpression]) -> str:
    return ns.s_exp_to_python(code, node_hooks)


def s_exp_to_python_ast(code: Union[str, ns.SExpression]) -> PythonAST:
    return ns.s_exp_to_python_ast(code, node_hooks)


python_to_python_ast = ns.python_to_python_ast
python_statement_to_python_ast = ns.python_statement_to_python_ast
python_statements_to_python_ast = ns.python_statements_to_python_ast


def to_type_annotated_ns_s_exp(
    code: PythonAST, dfa: dict, start_state: str
) -> ns.SExpression:
    return ns.to_type_annotated_ns_s_exp(code, dfa, start_state, non_sequence_prefixes)
