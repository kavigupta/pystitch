from collections import defaultdict
from dataclasses import dataclass, field
from types import NoneType
from typing import Callable, Dict, List, Set, Tuple, Union

import neurosym as ns
import numpy as np

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
                assert isinstance(node, ns.SExpression)
                symbol, state, *_ = node.symbol.split(SEPARATOR)
                state = ns.python_ast_tools.unclean_type(state)
                if ns.python_ast_tools.is_sequence(state, symbol):
                    self._lengths_by_sequence_type[state].add(len(node.children))
                elif len(node.children) == 0:
                    self._leaves[state].add(symbol)

    @classmethod
    def from_s_exps(cls, s_exps):
        """
        Factory version of add_s_exps.
        """
        subset = cls()
        subset.add_s_exps(*s_exps)
        return subset

    def add_programs(
        self,
        dfa,
        *programs: Tuple[ns.PythonAST, ...],
        root: Union[str, Tuple[str, ...]],
    ):
        """
        Add the programs to the subset. The root symbol of the DSL is passed as an argument,
            and can be a single string or a tuple of strings.

        Args:
            dfa: the dfa of the DSL
            programs: the programs to extract the subset from
            root: the root symbol of the DSL. If a tuple is passed, it must
                be the same length as the programs, providing a root symbol for each program.
            abstrs: abstractions: their bodies will be added to the list of programs
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

    @classmethod
    def from_programs(
        cls, dfa, *programs: Tuple[ns.PythonAST, ...], root: Union[str, Tuple[str, ...]]
    ):
        """
        Factory version of add_programs.
        """
        subset = cls()
        subset.add_programs(dfa, *programs, root=root)
        return subset

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
    """
    Yield all the nodes in the s-expression.
    """
    yield s_exp
    for child in s_exp.children:
        yield from traverse(child)


def create_dsl(
    dfa: dict,
    dsl_subset: DSLSubset,
    start_state: str,
    add_additional_productions: Callable[[ns.DSLFactory], NoneType] = lambda dslf: None,
):
    """
    Create a DSL from a DFA and a subset of the DSL.

    Args:
        dfa: the DFA of the DSL
        dsl_subset: the subset of the DSL
        start_state: the start state of the DSL
        add_additional_productions: a function that adds additional productions to the DSL

    Returns:
        the DSL
    """
    dslf = ns.DSLFactory()
    for target in dfa:
        for prod in dfa[target]:
            input_types = [ns.parse_type(t) for t in dfa[target][prod]]
            if ns.python_ast_tools.is_sequence(target, prod):
                assert len(input_types) == 1
                for length in dsl_subset.lengths_by_sequence_type.get(target, []):
                    typ = ns.ArrowType(input_types * length, ns.parse_type(target))
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
                typ = ns.ArrowType(tuple(input_types), ns.parse_type(target))
                dslf.concrete(
                    prod + SEPARATOR + ns.python_ast_tools.clean_type(target),
                    ns.render_type(typ),
                    None,
                )
    for target, leaves in dsl_subset.leaves.items():
        for constant in leaves:
            typ = ns.ArrowType((), ns.parse_type(target))
            dslf.concrete(constant + SEPARATOR + target, ns.render_type(typ), None)
    add_additional_productions(dslf)
    dslf.prune_to(start_state, tolerate_pruning_entire_productions=True)
    return dslf.finalize()


def create_smoothing_mask(dsl_full, dsl_subset):
    """
    Create a mask that can be used to smooth the output of a model that uses the full DSL
        to the subset DSL.
    """
    symbols_full = dsl_full.ordered_symbols(include_root=True)
    symbols_subset = set(dsl_subset.ordered_symbols(include_root=True))
    return np.array([s in symbols_subset for s in symbols_full])
