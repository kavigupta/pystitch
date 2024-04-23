import neurosym as ns

from imperative_stitch.utils.def_use_mask.mask import DefUseChainPreorderMask
from imperative_stitch.utils.def_use_mask.names import NAME_REGEX
from imperative_stitch.utils.def_use_mask.ordering import PythonNodeOrdering
from imperative_stitch.utils.export_as_dsl import DSLSubset, create_dsl


def create_de_brujin(idx, num_explicit_vars):
    if idx <= num_explicit_vars:
        return ns.SExpression(f"dbvar-{idx}", ())
    return ns.SExpression(
        "dbvar-successor",
        (create_de_brujin(idx - 1, num_explicit_vars),),
    )


def get_idx(s_exp_de_bruijn):
    assert s_exp_de_bruijn.symbol.startswith("dbvar-")
    after = s_exp_de_bruijn.symbol[len("dbvar-") :]
    if after == "successor":
        assert len(s_exp_de_bruijn.children) == 1
        return get_idx(s_exp_de_bruijn.children[0]) + 1
    assert len(s_exp_de_bruijn.children) == 0
    return int(after)


def canonicalize_de_bruijn(program, dfa, root_node, abstrs, num_explicit_vars):
    s_exp = program.to_type_annotated_ns_s_exp(dfa, root_node)

    dsl = create_dsl(
        dfa, DSLSubset.from_program(dfa, program, root=root_node), root_node
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
        fam.tree_distribution_skeleton, s_exp, num_explicit_vars
    )


def canonicalize_de_bruijn_from_tree_dist(tree_dist, s_exp, num_explicit_vars):
    id_to_new = {}
    for node, _, mask in ns.collect_preorder_symbols(s_exp, tree_dist):
        node_sym = tree_dist.symbol_to_index[node.symbol]
        if not NAME_REGEX.match(node.symbol):
            continue
        assert not node.children
        currently_defined = get_defined_indices(mask)
        if node_sym not in currently_defined:
            de_brujin_idx = 0
        else:
            de_brujin_idx = len(currently_defined) - currently_defined.index(node_sym)
        id_to_new[id(node)] = create_de_brujin(de_brujin_idx, num_explicit_vars)

    def replace(node):
        if id(node) in id_to_new:
            return id_to_new[id(node)]
        return ns.SExpression(node.symbol, [replace(child) for child in node.children])

    return replace(s_exp)


def get_defined_indices(mask):
    assert isinstance(mask, ns.ConjunctionPreorderMask)
    assert len(mask.masks) == 2
    mask = mask.masks[-1]
    assert isinstance(mask, DefUseChainPreorderMask)
    currently_defined = mask.currently_defined_indices()
    return currently_defined


def uncanonicalize_de_brujin(s_exp_de_bruijn):
    if not s_exp_de_bruijn.symbol.startswith("dbvar-"):
        return ns.SExpression(
            s_exp_de_bruijn.symbol,
            [uncanonicalize_de_brujin(child) for child in s_exp_de_bruijn.children],
        )
    idx = get_idx(s_exp_de_bruijn)
    return ns.SExpression(f"const-&_{idx}:0~Name", ())
