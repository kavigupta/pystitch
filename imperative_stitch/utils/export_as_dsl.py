from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple, Union

import neurosym as ns
import numpy as np

from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.compress.manipulate_abstraction import (
    abstraction_calls_to_bodies,
)
from imperative_stitch.parser.python_ast import PythonAST
from imperative_stitch.utils.def_use_mask.extra_var import (
    canonicalized_python_name_as_leaf,
)
from imperative_stitch.utils.types import SEPARATOR, is_sequence


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
    def fit_dsl_to_programs_and_output_s_exps(
        cls,
        dfa,
        *programs: Tuple[PythonAST, ...],
        root: Union[str, Tuple[str, ...]],
        abstrs: Tuple[Abstraction] = (),
        to_s_exp=lambda program, dfa, root_sym: program.to_type_annotated_ns_s_exp(
            dfa, root_sym
        ),
        include_variables=False,
    ):
        """
        See from_program for details. This function returns both the programs and the subset.
        """
        num_programs = len(programs)
        programs, root = cls.create_program_list(*programs, root=root, abstrs=abstrs)
        programs = [
            to_s_exp(program, dfa, root_sym)
            for program, root_sym in zip(programs, root)
        ]

        subset = cls.from_type_annotated_s_exps(
            programs, include_variables=include_variables
        )
        return programs[:num_programs], subset

    @classmethod
    def from_program(
        cls,
        dfa,
        *programs: Tuple[PythonAST, ...],
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
                default it uses the PythonAST.to_type_annotated_ns_s_exp method.
        """
        _, subset = cls.fit_dsl_to_programs_and_output_s_exps(
            dfa,
            *programs,
            root=root,
            abstrs=abstrs,
            to_s_exp=to_s_exp,
            include_variables=include_variables,
        )
        return subset

    @classmethod
    def create_program_list(
        cls,
        *programs: Tuple[PythonAST, ...],
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
            abstraction_calls_to_bodies(a.body, abstrs_dict) for a in abstrs
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
                state = ns.python_ast_tools.unclean_type(state)
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
        from imperative_stitch.utils.def_use_mask.canonicalize_de_bruijn import (
            canonicalize_de_bruijn_batched,
        )

        programs_all, roots_all = cls.create_program_list(
            *programs, root=root, abstrs=abstrs
        )
        programs_all = canonicalize_de_bruijn_batched(
            programs_all, roots_all, dfa, abstrs, max_explicit_dbvar_index
        )
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
                        prod
                        + SEPARATOR
                        + ns.python_ast_tools.clean_type(target)
                        + SEPARATOR
                        + str(length),
                        ns.render_type(typ),
                        None,
                    )
            else:
                typ = ns.ArrowType(
                    tuple(ns.parse_type(x) for x in dfa[target][prod]),
                    ns.parse_type(target),
                )
                dslf.concrete(
                    prod + SEPARATOR + ns.python_ast_tools.clean_type(target),
                    ns.render_type(typ),
                    None,
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
