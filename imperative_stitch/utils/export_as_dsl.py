from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Union

import neurosym as ns
import numpy as np

from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.compress.manipulate_abstraction import (
    abstraction_calls_to_bodies,
)
from imperative_stitch.utils.types import SEPARATOR


@dataclass
class DSLSubset:
    """
    Represents a subset of the python DSL. This is represented as
        - a dictionary from sequential type to a list of lengths.
        - a dictionary from types to a list of leaves of that type
    """

    _lengths_by_sequence_type: Dict[str, Set[int]] = field(
        default_factory=lambda: defaultdict(set)
    )
    _leaves: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

    @property
    def lengths_by_sequence_type(self) -> Dict[str, List[int]]:
        return {k: sorted(v) for k, v in self._lengths_by_sequence_type.items()}

    @property
    def leaves(self) -> Dict[str, List[str]]:
        return {k: sorted(v) for k, v in self._leaves.items()}

    def add_s_exps(self, *s_exps):
        """
        Add the following s-expressions to the subset. They must be type-annotated.
        """
        for s_exp in s_exps:
            for node in traverse(s_exp):
                symbol, state, *_ = node.symbol.split(SEPARATOR)
                state = ns.python_ast_tools.unclean_type(state)
                assert isinstance(node, ns.SExpression)
                if ns.python_ast_tools.is_sequence(state, symbol):
                    self._lengths_by_sequence_type[state].add(len(node.children))
                elif len(node.children) == 0 and not symbol.startswith("fn_"):
                    self._leaves[state].add(symbol)

    def add_programs(
        self,
        dfa,
        *programs: Tuple[ns.PythonAST, ...],
        root: Union[str, Tuple[str, ...]],
    ):
        """
        Add the following programs to the subset. The root symbol of the program must be provided.
        """
        if isinstance(root, str):
            root = [root] * len(programs)
        else:
            if len(root) != len(programs):
                raise ValueError(
                    "The length of the root should be the same as the number of programs, but was"
                    f" {len(root)} and {len(programs)} respectively."
                )

        s_exps = []
        for program, root_sym in zip(programs, root):
            s_exp = ns.to_type_annotated_ns_s_exp(program, dfa, root_sym)
            self.add_s_exps(s_exp)
            s_exps.append(s_exp)
        return s_exps

    def add_abstractions(self, dfa, *abstrs: Tuple[Abstraction, ...]):
        """
        Add the bodies of the abstractions to the subset.
        """
        abstrs_dict = {a.name: a for a in abstrs}
        return self.add_programs(
            dfa,
            *[abstraction_calls_to_bodies(a.body, abstrs_dict) for a in abstrs],
            root=[a.dfa_root for a in abstrs],
        )

    @classmethod
    def from_program(
        cls,
        dfa,
        *programs: Tuple[ns.PythonAST, ...],
        root: Union[str, Tuple[str, ...]],
        abstrs: Tuple[Abstraction] = (),
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
        """
        subset = cls()
        subset.add_programs(dfa, *programs, root=root)
        subset.add_abstractions(dfa, *abstrs)
        return subset

    @classmethod
    def from_type_annotated_s_exps(cls, s_exps):
        """
        Construct a DSLSubset from a list of type-annotated s-expressions. Used by
            DSLSubset.from_program.
        """
        subset = cls()
        subset.add_s_exps(*s_exps)
        return subset

    @classmethod
    def from_programs_de_bruijn(
        cls, *programs, roots, dfa, abstrs, max_explicit_dbvar_index
    ):
        # pylint: disable=cyclic-import
        from imperative_stitch.utils.def_use_mask.canonicalize_de_bruijn import (
            canonicalize_de_bruijn_batched,
        )

        assert len(programs) == len(
            roots
        ), "The number of programs and roots must match."

        programs_all = canonicalize_de_bruijn_batched(
            programs,
            roots,
            dfa,
            abstrs,
            max_explicit_dbvar_index,
            include_abstr_exprs=True,
        )
        subset = cls.from_type_annotated_s_exps(programs_all)
        return programs_all[: len(programs)], subset

    def fill_in_missing_lengths(self):
        """
        Fill in "missing lengths" for each sequence type. E.g., if the lengths
            of a sequence type are [1, 3], this function will add 2 to the list.
        """
        self._lengths_by_sequence_type = {
            seq_type: set(range(min(lengths), max(lengths) + 1))
            for seq_type, lengths in self.lengths_by_sequence_type.items()
        }


def traverse(s_exp):
    yield s_exp
    for child in s_exp.children:
        yield from traverse(child)


def create_dsl(dfa, dsl_subset, start_state, dslf=None, include_dbvars=False):
    # pylint: disable=cyclic-import
    from .def_use_mask.canonicalize_de_bruijn import (
        dbvar_successor_symbol,
        dbvar_wrapper_symbol_by_root_type,
    )

    if dslf is None:
        dslf = ns.DSLFactory()
    for target in dfa:
        for prod in dfa[target]:
            if ns.python_ast_tools.is_sequence(target, prod):
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
    if include_dbvars:
        dslf.concrete(dbvar_successor_symbol, "DBV -> DBV", None)
        for root_type, sym in dbvar_wrapper_symbol_by_root_type.items():
            dslf.concrete(sym, f"DBV -> {root_type}", None)
    dslf.prune_to(start_state, tolerate_pruning_entire_productions=True)
    return dslf.finalize()


def create_smoothing_mask(dsl_full, dsl_subset):
    symbols_full = dsl_full.ordered_symbols(include_root=True)
    symbols_subset = set(dsl_subset.ordered_symbols(include_root=True))
    return np.array([s in symbols_subset for s in symbols_full])
