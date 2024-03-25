import copy
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple

import neurosym as ns

from imperative_stitch.parser.parsed_ast import ParsedAST

from .classify_nodes import BAD_TYPES, classify_nodes_in_program

SEPARATOR = "~"


@dataclass
class DSLSubset:
    """
    Represents a subset of the python DSL. This is represented as
        - a dictionary from sequential type to a list of lengths.
        - a dictionary from types to a list of leaves of that type
    """

    lengths_by_sequence_type: Dict[str, List[int]]
    leaves: Dict[str, List[str]]

    @classmethod
    def from_program(cls, dfa, *programs: Tuple[ParsedAST, ...], root: str):
        lengths_by_list_type = defaultdict(set)
        leaves = defaultdict(set)
        for program in programs:
            code = program.to_ns_s_exp(dict(no_leaves=True))
            for node, state in list(classify_nodes_in_program(dfa, code, root)):
                assert isinstance(node, ns.SExpression)
                if is_sequence(state, node.symbol):
                    lengths_by_list_type[state].add(len(node.children))
                elif len(node.children) == 0 and not node.symbol.startswith("fn_"):
                    leaves[state].add(node.symbol)
        return cls(
            lengths_by_sequence_type={
                k: sorted(v) for k, v in lengths_by_list_type.items()
            },
            leaves={k: sorted(v) for k, v in leaves.items()},
        )


def is_sequence_type(x):
    x = ns.parse_type(x)
    if isinstance(x, ns.ListType):
        return True
    if not isinstance(x, ns.AtomicType):
        return False
    return x.name == "seqS"


def is_sequence_symbol(x):
    return x in ["/seq", "/subseq", "list", "/choiceseq"]


def is_sequence(type_name, head_symbol):
    if head_symbol.startswith("fn_") or head_symbol.startswith("var-"):
        return False
    seq_type = is_sequence_type(type_name)
    seq_symbol = is_sequence_symbol(head_symbol)
    assert seq_type == seq_symbol or type_name in BAD_TYPES, (
        seq_type,
        seq_symbol,
        type_name,
        head_symbol,
    )
    return seq_type


def clean_type(x):
    """
    Replace [] with __ in the type name
    """
    return x.replace("[", "_").replace("]", "_")


def create_dsl(dfa, dsl_subset, start_state, dslf=None):
    if dslf is None:
        dslf = ns.DSLFactory()
    for target in dfa:
        for prod in dfa[target]:
            if is_sequence(target, prod):
                assert len(dfa[target][prod]) == 1
                for length in dsl_subset.lengths_by_sequence_type.get(target, []):
                    typ = ns.ArrowType(
                        (ns.parse_type(dfa[target][prod][0]),) * length,
                        ns.parse_type(target),
                    )
                    dslf.concrete(
                        prod + SEPARATOR + clean_type(target) + SEPARATOR + str(length),
                        ns.render_type(typ),
                        None,
                    )
            else:
                typ = ns.ArrowType(
                    tuple(ns.parse_type(x) for x in dfa[target][prod]),
                    ns.parse_type(target),
                )
                dslf.concrete(
                    prod + SEPARATOR + clean_type(target), ns.render_type(typ), None
                )
    for target, leaves in dsl_subset.leaves.items():
        for constant in leaves:
            typ = ns.ArrowType((), ns.parse_type(target))
            dslf.concrete(constant + SEPARATOR + target, ns.render_type(typ), None)
    dslf.prune_to(start_state, tolerate_pruning_entire_productions=True)
    return dslf.finalize()


def add_disambiguating_type_tags(dfa, prog, start_state):
    prog = copy.deepcopy(prog)
    node_id_to_new_symbol = {}
    for node, tag in classify_nodes_in_program(dfa, prog, start_state):
        assert isinstance(node, ns.SExpression), node
        new_symbol = node.symbol + SEPARATOR + clean_type(tag)
        if is_sequence(tag, node.symbol):
            new_symbol += SEPARATOR + str(len(node.children))
        node_id_to_new_symbol[id(node)] = new_symbol
    return replace_symbols(prog, node_id_to_new_symbol)


def replace_symbols(program, id_to_sym):
    return ns.SExpression(
        id_to_sym[id(program)],
        tuple(replace_symbols(c, id_to_sym) for c in program.children),
    )
