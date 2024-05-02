import copy
import re
from dataclasses import dataclass
from typing import List

import neurosym as ns

from imperative_stitch.utils.def_use_mask.mask import DefUseChainPreorderMask
from imperative_stitch.utils.def_use_mask.names import NAME_REGEX
from imperative_stitch.utils.def_use_mask.ordering import PythonNodeOrdering
from imperative_stitch.utils.export_as_dsl import (
    SEPARATOR,
    DSLSubset,
    create_dsl,
    get_dfa_state,
)

dbv_type = "DBV"


def dbvar_symbol(idx):
    return f"dbvar-{idx}{SEPARATOR}{dbv_type}"


dbvar_symbol_regex = re.compile(
    r"dbvar-(\d+|successor)" + "(" + re.escape(SEPARATOR) + re.escape(dbv_type) + ")?"
)

dbvar_successor_symbol = dbvar_symbol("successor")

dbvar_wrapper_symbol_by_root_type = {
    root_type: f"dbvar{SEPARATOR}{root_type}"
    for root_type in ("Name", "NullableName", "NameStr", "NullableNameStr")
}


def is_dbvar_wrapper_symbol(symbol):
    return symbol in dbvar_wrapper_symbol_by_root_type.values()


def canonicalized_python_name(name):
    return f"__{name}"


def canonicalized_python_name_as_leaf(name, use_type=False):
    """
    Get the canonicalized python name as a leaf node. E.g., __0
    """
    result = f"const-&{canonicalized_python_name(name)}:0"
    if use_type:
        # TODO - this is a bit of a hack, since we should really be using use_type
        # however, this would require us to add use_type to the program
        result += SEPARATOR + "Name"
    return result


def create_de_brujin_child(idx, de_bruijn_limit):
    """
    Create a de bruijn child. to be placed into a wrapper.
    """
    if idx <= de_bruijn_limit:
        return ns.SExpression(dbvar_symbol(idx), ())
    return ns.SExpression(
        dbvar_successor_symbol,
        (create_de_brujin_child(idx - 1, de_bruijn_limit),),
    )


def create_de_brujin(idx, de_bruijn_limit, dfa_sym):
    """
    Create a de bruijn name.
    """
    return ns.SExpression(
        dbvar_wrapper_symbol_by_root_type[dfa_sym],
        (create_de_brujin_child(idx, de_bruijn_limit),),
    )


def get_idx(s_exp_de_bruijn):
    """
    Get the index of the given de bruijn variable.
    """
    if is_dbvar_wrapper_symbol(s_exp_de_bruijn.symbol):
        assert len(s_exp_de_bruijn.children) == 1, s_exp_de_bruijn
        return get_idx(s_exp_de_bruijn.children[0])
    mat = dbvar_symbol_regex.match(s_exp_de_bruijn.symbol)
    assert mat, s_exp_de_bruijn.symbol
    after = mat.group(1)
    if after == "successor":
        assert len(s_exp_de_bruijn.children) == 1
        return get_idx(s_exp_de_bruijn.children[0]) + 1
    assert len(s_exp_de_bruijn.children) == 0
    return int(after)


def canonicalize_de_bruijn(program, dfa, root_node, abstrs, de_bruijn_limit):
    """
    Convert the program to a de bruijn representation. Creates a tree distribution
        and then calls the canonicalize_de_bruijn_from_tree_dist function.
    """

    check_have_all_abstrs(dfa, abstrs)

    s_exp = program.to_type_annotated_ns_s_exp(dfa, root_node)
    abstrs_dict = {abstr.name: abstr for abstr in abstrs}
    abstr_bodies = [
        abstr.body.abstraction_calls_to_bodies(abstrs_dict).to_type_annotated_ns_s_exp(
            dfa, abstr.dfa_root
        )
        for abstr in abstrs
    ]

    dsl = create_dsl(
        dfa, DSLSubset.from_type_annotated_s_exps([s_exp] + abstr_bodies), root_node
    )
    fam = ns.BigramProgramDistributionFamily(
        dsl,
        additional_preorder_masks=[
            lambda dist, dsl: DefUseChainPreorderMask(dist, dsl, dfa=dfa, abstrs=abstrs)
        ],
        include_type_preorder_mask=True,
        node_ordering=lambda dist: PythonNodeOrdering(dist, abstrs),
    )
    return canonicalize_de_bruijn_from_tree_dist(
        fam.tree_distribution_skeleton, s_exp, de_bruijn_limit
    )


def check_have_all_abstrs(dfa, abstrs):
    abstr_names = {abstr.name for abstr in abstrs}
    for vs in dfa.values():
        for v in vs:
            if not v.startswith("fn_"):
                continue
            assert (
                v in abstr_names
            ), f"Missing abstraction {v} in abstrs. Have {sorted(abstr_names)}"


def canonicalize_de_bruijn_from_tree_dist(tree_dist, s_exp, de_bruijn_limit):
    """
    Convert the program to a de bruijn representation, given the tree distribution.
    """
    id_to_new = {}
    for node, _, mask in ns.collect_preorder_symbols(s_exp, tree_dist):
        node_sym = tree_dist.symbol_to_index[node.symbol]
        mat = NAME_REGEX.match(node.symbol)
        if not mat:
            continue
        assert not node.children
        currently_defined = get_defined_indices(mask)
        if node_sym not in currently_defined:
            de_brujin_idx = 0
        else:
            de_brujin_idx = len(currently_defined) - currently_defined.index(node_sym)
        id_to_new[id(node)] = create_de_brujin(
            de_brujin_idx, de_bruijn_limit, mat.group("dfa_sym")
        )

    def replace(node):
        if id(node) in id_to_new:
            return id_to_new[id(node)]
        return ns.SExpression(node.symbol, [replace(child) for child in node.children])

    return replace(s_exp)


def get_defined_indices(mask):
    """
    Get the set of defined indices for a given mask.
    """
    assert isinstance(mask, ns.ConjunctionPreorderMask)
    assert len(mask.masks) == 2
    mask = mask.masks[-1]
    assert isinstance(mask, DefUseChainPreorderMask)
    currently_defined = mask.currently_defined_indices()
    return currently_defined


def uncanonicalize_de_bruijn(dfa, s_exp_de_bruijn, abstrs):
    """
    Uncanonicalize the de bruijn representation, replacing variables
        with names __0, __1, etc.
    """
    if isinstance(s_exp_de_bruijn, str):
        s_exp_de_bruijn = ns.parse_s_expression(s_exp_de_bruijn)
    else:
        assert isinstance(s_exp_de_bruijn, ns.SExpression)
        s_exp_de_bruijn = copy.deepcopy(s_exp_de_bruijn)

    abstrs_dict = {abstr.name: abstr for abstr in abstrs}
    abstr_bodies = [
        abstr.body.abstraction_calls_to_bodies(abstrs_dict).to_type_annotated_ns_s_exp(
            dfa, abstr.dfa_root
        )
        for abstr in abstrs
    ]

    dsl = create_dsl(
        dfa,
        DSLSubset.from_type_annotated_s_exps([s_exp_de_bruijn] + abstr_bodies),
        get_dfa_state(s_exp_de_bruijn.symbol),
    )
    fam = ns.BigramProgramDistributionFamily(
        dsl,
        additional_preorder_masks=[
            lambda dist, dsl: DefUseChainPreorderMask(dist, dsl, dfa=dfa, abstrs=abstrs)
        ],
        include_type_preorder_mask=True,
        node_ordering=lambda dist: PythonNodeOrdering(dist, abstrs),
    )
    tree_dist = fam.tree_distribution_skeleton

    count_vars = 0

    def replace_de_brujin(node, mask, typ):
        """
        Compute the replacement for a de bruijn node.
        """
        nonlocal count_vars
        indices = get_defined_indices(mask)
        idx = get_idx(node)
        if idx == 0:
            result = ns.SExpression(
                canonicalized_python_name_as_leaf(count_vars, use_type=typ), ()
            )
            count_vars += 1
            return result
        sym_idx = indices[-idx]
        sym, _ = tree_dist.symbols[sym_idx]
        return ns.SExpression(sym, ())

    id_to_new = {}

    def traverse_replacer(node, mask):
        if is_dbvar_wrapper_symbol(node.symbol):
            assert len(node.children) == 1
            new_node = replace_de_brujin(
                node.children[0], mask, node.symbol.split(SEPARATOR)[-1]
            )
            id_to_new[id(node)] = new_node
            return new_node
        return node

    list(
        ns.collect_preorder_symbols(
            s_exp_de_bruijn,
            tree_dist,
            replace_node_midstream=traverse_replacer,
        )
    )

    def replace(node):
        if id(node) in id_to_new:
            return id_to_new[id(node)]
        return ns.SExpression(node.symbol, [replace(child) for child in node.children])

    return replace(s_exp_de_bruijn)


def compute_de_bruijn_limit(tree_dist: ns.TreeDistribution) -> int:
    """
    Compute the de bruijn limit for the given tree distribution.
    """
    dbvars = []
    for x, _ in tree_dist.symbols:
        mat = dbvar_symbol_regex.match(x)
        if mat and mat.group(1) != "successor":
            dbvars.append(x)
    if not dbvars:
        return 0
    return len(dbvars) - 1


@dataclass
class DeBruijnMaskHandler:
    """
    Handles the mask behavior of de bruijin nodes.
    """

    tree_dist: ns.TreeDistribution
    de_bruijn_limit: int
    num_available_symbols: int
    level_nesting: int = 1
    inside_successor: bool = False
    dbvar_value: int = 0

    def compute_mask(self, symbols: List[int], is_defn):
        """
        Compute the mask for the given symbols.
        """
        mask = {}
        if self.inside_successor:
            # We are inside a successor, so the de bruijn limit is valid, as is successor
            mask[dbvar_symbol(self.de_bruijn_limit)] = True
            mask[dbvar_successor_symbol] = True
        else:
            # We are not inside a successor, so we need to iterate upwards
            start_at = 0 if is_defn else 1
            for i in range(start_at, self.num_available_symbols - self.dbvar_value + 1):
                if i > self.de_bruijn_limit:
                    mask[dbvar_successor_symbol] = True
                    break
                mask[dbvar_symbol(i)] = True
        mask = [mask.get(self.tree_dist.symbols[sym][0], False) for sym in symbols]
        return mask

    def on_entry(self, symbol):
        """
        Handle the entry of a symbol.
        """
        self.level_nesting += 1
        if self.tree_dist.symbols[symbol][0] == dbvar_successor_symbol:
            self.inside_successor = True
            self.dbvar_value += 1
            return
        self.dbvar_value += int(
            self.tree_dist.symbols[symbol][0].split("-")[-1].split("~")[0]
        )

    def on_exit(self, symbol):
        """
        Handle the exit of a symbol.
        """
        self.level_nesting -= 1
        if self.level_nesting > 0:
            return None
        sym = self.tree_dist.symbols[symbol][0]
        assert is_dbvar_wrapper_symbol(sym)
        symbol = self.tree_dist.symbol_to_index[
            canonicalized_python_name_as_leaf(
                self.num_available_symbols - self.dbvar_value,
                use_type=sym.split(SEPARATOR)[-1],
            )
        ]
        return symbol
