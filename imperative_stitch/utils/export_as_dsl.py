import copy
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple, Union

import neurosym as ns
import numpy as np

from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.parser.parsed_ast import ParsedAST
from imperative_stitch.utils.def_use_mask.extra_var import (
    canonicalized_python_name_as_leaf,
)
from imperative_stitch.utils.types import SEPARATOR

from .classify_nodes import BAD_TYPES, classify_nodes_in_program


@dataclass
class DSLSubset:
    """
    Represents a subset of the python DSL. This is represented as
        - a dictionary from sequential type to a list of lengths.
        - a dictionary from types to a list of leaves of that type
    """

    lengths_by_sequence_type: Dict[str, List[int]]
    leaves: Dict[str, List[str]]
    include_dbvars: bool

    @classmethod
    def from_program(
        cls,
        dfa,
        *programs: Tuple[ParsedAST, ...],
        root: Union[str, Tuple[str, ...]],
        abstrs: Tuple[Abstraction] = (),
        to_s_exp=lambda program, dfa, root_sym: program.to_type_annotated_ns_s_exp(
            dfa, root_sym
        ),
        include_variables=False,
    ):
        """
        Construct a DSLSubset from a list of programs. The subset contains all the
            sequence lengths and leaves that appear in the programs.

        Args:
            dfa: the dfa of the DSL
            programs: the programs to extract the subset from
            root: the root symbol of the DSL. If a tuple is passed, it must
                be the same length as the programs, providing a root symbol for each program.
            abstrs: abstractions: their bodies will be added to the list of programs
            to_s_exp: a function that converts a program to a type-annotated s-expression. By
                default it uses the ParsedAST.to_type_annotated_ns_s_exp method.
        """
        programs, root = cls.create_program_list(*programs, root=root, abstrs=abstrs)
        programs = [
            to_s_exp(program, dfa, root_sym)
            for program, root_sym in zip(programs, root)
        ]

        return cls.from_type_annotated_s_exps(
            programs, include_variables=include_variables
        )

    @classmethod
    def create_program_list(
        cls,
        *programs: Tuple[ParsedAST, ...],
        root: Union[str, Tuple[str, ...]],
        abstrs: Tuple[Abstraction] = (),
    ):
        if isinstance(root, tuple):
            if len(root) != len(programs):
                raise ValueError(
                    "The length of the root should be the same as the number of programs, but was"
                    f" {len(root)} and {len(programs)} respectively."
                )
            root = list(root)
        else:
            assert isinstance(root, str)
            root = [root] * len(programs)
        abstrs_dict = {a.name: a for a in abstrs}
        programs = list(programs) + [
            a.body.abstraction_calls_to_bodies(abstrs_dict) for a in abstrs
        ]
        root += [a.dfa_root for a in abstrs]
        return programs, root

    @classmethod
    def from_type_annotated_s_exps(cls, s_exps, *, include_variables=False):
        """
        Construct a DSLSubset from a list of type-annotated s-expressions. Used by
            DSLSubset.from_program.
        """
        # pylint: disable=cyclic-import
        from .def_use_mask.canonicalize_de_bruijn import create_de_bruijn_child

        de_bruijn_new = create_de_bruijn_child(0, 1).symbol
        num_vars = 0
        lengths_by_list_type = defaultdict(set)
        leaves = defaultdict(set)
        for program in s_exps:
            for node in traverse(program):
                if node.symbol == de_bruijn_new:
                    num_vars += 1
                symbol, state, *_ = node.symbol.split(SEPARATOR)
                state = unclean_type(state)
                assert isinstance(node, ns.SExpression)
                if is_sequence(state, symbol):
                    lengths_by_list_type[state].add(len(node.children))
                elif len(node.children) == 0 and not symbol.startswith("fn_"):
                    leaves[state].add(symbol)
        if include_variables:
            for var in range(num_vars):
                leaves["Name"].add(canonicalized_python_name_as_leaf(var))
        return cls(
            lengths_by_sequence_type={
                k: sorted(v) for k, v in lengths_by_list_type.items()
            },
            leaves={k: sorted(v) for k, v in leaves.items()},
            include_dbvars=num_vars > 0,
        )

    @classmethod
    def from_programs_de_bruijn(
        cls, *programs, root, dfa, abstrs, max_explicit_dbvar_index
    ):
        programs_all, roots_all = cls.create_program_list(
            *programs, root=root, abstrs=abstrs
        )
        programs_all = [
            x.to_type_annotated_de_bruijn_ns_s_exp(
                dfa,
                root,
                max_explicit_dbvar_index=max_explicit_dbvar_index,
                abstrs=abstrs,
            )
            for x, root in zip(programs_all, roots_all)
        ]
        subset = cls.from_type_annotated_s_exps(programs_all)
        return programs_all[: len(programs)], subset

    def fill_in_missing_lengths(self):
        """
        Fill in "missing lengths" for each sequence type. E.g., if the lengths
            of a sequence type are [1, 3], this function will add 2 to the list.
        """
        lengths_new = {
            seq_type: list(range(min(lengths), max(lengths) + 1))
            for seq_type, lengths in self.lengths_by_sequence_type.items()
        }
        return DSLSubset(
            lengths_by_sequence_type=lengths_new,
            leaves=self.leaves,
            include_dbvars=self.include_dbvars,
        )


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
    from .def_use_mask.canonicalize_de_bruijn import (
        dbvar_successor_symbol,
        dbvar_wrapper_symbol_by_root_type,
    )

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
    if dsl_subset.include_dbvars:
        dslf.concrete(dbvar_successor_symbol, "DBV -> DBV", None)
        for root_type, sym in dbvar_wrapper_symbol_by_root_type.items():
            dslf.concrete(sym, f"DBV -> {root_type}", None)
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


def replace_nodes(program, id_to_node):
    if id(program) in id_to_node:
        return id_to_node[id(program)]
    return ns.SExpression(
        program.symbol,
        tuple(replace_nodes(c, id_to_node) for c in program.children),
    )
