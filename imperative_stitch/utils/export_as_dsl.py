import copy
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple, Union

import neurosym as ns
import numpy as np

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
    def from_program(
        cls, dfa, *programs: Tuple[ParsedAST, ...], root: Union[str, Tuple[str, ...]]
    ):
        """
        Construct a DSLSubset from a list of programs. The subset contains all the
            sequence lengths and leaves that appear in the programs.

        Args:
            dfa: the dfa of the DSL
            programs: the programs to extract the subset from
            root: the root symbol of the DSL. If a tuple is passed, it must
                be the same length as the programs, providing a root symbol for each program.
        """
        if isinstance(root, tuple):
            if len(root) != len(programs):
                raise ValueError(
                    "The length of the root should be the same as the number of programs, but was"
                    f" {len(root)} and {len(programs)} respectively."
                )
        else:
            assert isinstance(root, str)
            root = (root,) * len(programs)
        programs = [
            program.to_type_annotated_ns_s_exp(dfa, root_sym)
            for program, root_sym in zip(programs, root)
        ]
        return cls.from_type_annotated_s_exps(programs)

    @classmethod
    def from_type_annotated_s_exps(cls, s_exps):
        """
        Construct a DSLSubset from a list of type-annotated s-expressions. Used by
            DSLSubset.from_program.
        """
        from .def_use_mask.canonicalize_de_bruijn import (
            canonicalized_python_name_as_leaf,
            create_de_brujin,
        )

        de_brujin_new = create_de_brujin(0, 1).symbol
        num_vars = 0
        lengths_by_list_type = defaultdict(set)
        leaves = defaultdict(set)
        for program in s_exps:
            for node in traverse(program):
                if node.symbol == de_brujin_new:
                    num_vars += 1
                symbol, state, *_ = node.symbol.split(SEPARATOR)
                state = unclean_type(state)
                assert isinstance(node, ns.SExpression)
                if is_sequence(state, symbol):
                    lengths_by_list_type[state].add(len(node.children))
                elif len(node.children) == 0 and not symbol.startswith("fn_"):
                    leaves[state].add(symbol)
        for var in range(num_vars):
            leaves["Name"].add(canonicalized_python_name_as_leaf(var))
        return cls(
            lengths_by_sequence_type={
                k: sorted(v) for k, v in lengths_by_list_type.items()
            },
            leaves={k: sorted(v) for k, v in leaves.items()},
        )

    def fill_in_missing_lengths(self):
        """
        Fill in "missing lengths" for each sequence type. E.g., if the lengths
            of a sequence type are [1, 3], this function will add 2 to the list.
        """
        lengths_new = {
            seq_type: list(range(min(lengths), max(lengths) + 1))
            for seq_type, lengths in self.lengths_by_sequence_type.items()
        }
        return DSLSubset(lengths_by_sequence_type=lengths_new, leaves=self.leaves)


def get_dfa_state(sym):
    return sym.split(SEPARATOR)[1]


def traverse(s_exp):
    yield s_exp
    for child in s_exp.children:
        yield from traverse(child)


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
    return seq_type or seq_symbol


def clean_type(x):
    """
    Replace [] with __ in the type name
    """
    return x.replace("[", "_").replace("]", "_")


def unclean_type(x):
    """
    Replace __ with [] in the type name
    """
    if "_" not in x:
        return x
    assert x.count("_") == 2, x
    return x.replace("_", "[", 1).replace("_", "]", 1)


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


def create_smoothing_mask(dsl_full, dsl_subset):
    symbols_full = dsl_full.ordered_symbols(include_root=True)
    symbols_subset = set(dsl_subset.ordered_symbols(include_root=True))
    return np.array([s in symbols_subset for s in symbols_full])


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
